# Install https://github.com/slackapi/python-slackclient
# Install https://github.com/ageitgey/face_recognition

import os
import time
import re
from slackclient import SlackClient
import requests
from PIL import Image, ImageDraw
import face_recognition

def resize_image(image, ratio):
    (h, w) = image.size
    image = image.resize(((int)(h*ratio),(int)(w*ratio)), Image.ANTIALIAS)
    return image
    # filen = file_name + '.png', 'PNG'
    # image.save(filen, 'PNG')
    # return filen


def makeupify(file_name):
    image = Image.open(file_name)
    image = resize_image(image, 2)
    tmp_name = file_name + '.tmp.png'
    image.save(tmp_name, 'PNG')

    # tmp_name=file_name

    # Load the jpg file into a numpy array
    image = face_recognition.load_image_file(tmp_name)
    
    # Find all facial features in all the faces in the image
    face_landmarks_list = face_recognition.face_landmarks(image)

    pil_image = Image.fromarray(image)
    for face_landmarks in face_landmarks_list:
        d = ImageDraw.Draw(pil_image, 'RGBA')

        # Make the eyebrows into a nightmare
        # d.polygon(face_landmarks['left_eyebrow'], fill=(68, 54, 39, 128))
        # d.polygon(face_landmarks['right_eyebrow'], fill=(68, 54, 39, 128))
        d.line(face_landmarks['left_eyebrow'], fill=(68, 54, 39, 150), width=8)
        d.line(face_landmarks['right_eyebrow'], fill=(68, 54, 39, 150), width=8)

        # Gloss the lips
        d.polygon(face_landmarks['top_lip'], fill=(150, 0, 0, 128))
        d.polygon(face_landmarks['bottom_lip'], fill=(150, 0, 0, 128))
        d.line(face_landmarks['top_lip'], fill=(150, 0, 0, 64), width=1)
        d.line(face_landmarks['bottom_lip'], fill=(150, 0, 0, 64), width=1)

        # Sparkle the eyes
        d.polygon(face_landmarks['left_eye'], fill=(255, 255, 255, 30))
        d.polygon(face_landmarks['right_eye'], fill=(255, 255, 255, 30))

        # Apply some eyeliner
        d.line(face_landmarks['left_eye'] + [face_landmarks['left_eye'][0]], fill=(0, 0, 0, 110), width=4)
        d.line(face_landmarks['right_eye'] + [face_landmarks['right_eye'][0]], fill=(0, 0, 0, 110), width=4)

    pil_image = resize_image(pil_image, 0.5)
    pil_image.save(file_name + '_makeup.png', 'PNG')
    return file_name + '_makeup.png'


# instantiate Slack client
slack_client = SlackClient(os.environ.get('SLACK_BOT_TOKEN'))
# starterbot's user ID in Slack: value is assigned after the bot starts up
starterbot_id = None

# constants
RTM_READ_DELAY = 1 # 1 second delay between reading from RTM
EXAMPLE_COMMAND = "do"
MENTION_REGEX = "^<@(|[WU].+?)>(.*)"

last_event = None
def parse_bot_commands(slack_events):
    """
        Parses a list of events coming from the Slack RTM API to find bot commands.
        If a bot command is found, this function returns a tuple of command and channel.
        If its not found, then this function returns None, None.
    """
    for event in slack_events:
        print(event["type"])
        print(event)
        if event["type"] == "message" and event["subtype"] == "file_share":
            if event["user"] == starterbot_id:
                continue

            print("calling files.info")
            file_info = slack_client.api_call(
                "files.info",
                file=event["file"]["id"],
            )
            img_name = event["file"]["id"] + '.jpg'
            with open(img_name, 'wb') as handle:
                headers = {}
                headers["Authorization"] = 'Bearer ' + os.environ.get('SLACK_BOT_TOKEN')
                response = requests.get(
                    file_info["file"]["url_private_download"],
                    stream=True,
                    headers=headers
                )

                if not response.ok:
                    print(response)

                for block in response.iter_content(1024):
                    if not block:
                        break

                    handle.write(block)

            makeup_name = makeupify(img_name)
            with open(makeup_name, 'rb') as file_content:
                slack_client.api_call(
                    "files.upload",
                    channels=event["channel"],
                    file=file_content,
                    title="test upload"
                )

            print("setting event")
            last_event = event
                
        elif event["type"] == "message" and not "subtype" in event:
            print("setting event")
            last_event = event
            print(event["text"])
            user_id, message = parse_direct_mention(event["text"])
            if user_id == starterbot_id:
                return message, event["channel"]
        else:
            print("setting event")
            last_event = event

    return None, None

def parse_direct_mention(message_text):
    """
        Finds a direct mention (a mention that is at the beginning) in message text
        and returns the user ID which was mentioned. If there is no direct mention, returns None
    """
    matches = re.search(MENTION_REGEX, message_text)
    # the first group contains the username, the second group contains the remaining message
    return (matches.group(1), matches.group(2).strip()) if matches else (None, None)

def handle_command(command, channel):
    """
        Executes bot command if the command is known
    """
    # Default response is help text for the user
    default_response = "Not sure what you mean. Try *{}*.".format(EXAMPLE_COMMAND)

    # Finds and executes the given command, filling in response
    response = None
    # This is where you start to implement more commands!
    if command.startswith(EXAMPLE_COMMAND):
        response = "Sure...write some more code then I can do that!"

    # Sends the response back to the channel
    slack_client.api_call(
        "chat.postMessage",
        channel=channel,
        text=response or default_response
    )

if __name__ == "__main__":
    # makeupify('Captureinsta.PNG')
    if slack_client.rtm_connect(with_team_state=False):
        print("Starter Bot connected and running!")
        # Read bot's user ID by calling Web API method `auth.test`
        starterbot_id = slack_client.api_call("auth.test")["user_id"]
        print(starterbot_id)
        while True:
            command, channel = parse_bot_commands(slack_client.rtm_read())
            if command:
                handle_command(command, channel)
            time.sleep(RTM_READ_DELAY)
    else:
        print("Connection failed. Exception traceback printed above.")

