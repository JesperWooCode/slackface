#!/usr/bin/env python3
# Install https://github.com/slackapi/python-slackclient
# Install https://github.com/ageitgey/face_recognition

import os
import time
from slackclient import SlackClient
import requests
from PIL import Image, ImageDraw
import face_recognition
import numpy as np
from io import BytesIO
from operator import itemgetter
from random import randint, random
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

SLACK_BOT_TOKEN = os.getenv('SLACK_BOT_TOKEN')
if not SLACK_BOT_TOKEN:
    exit()

def resize_image(image, ratio):
    (h, w) = image.size
    if h * w > 1000 * 1000:
        return image
    return image.resize(((int)(h*ratio),(int)(w*ratio)), Image.ANTIALIAS)

def extrapolate(x1, y1, x2, y2, newx):
    return (newx, y1+(newx-x1)/(x2-x1)*(y2-y1))
    
def niceeyebrow(arr):
    maxx = max(arr, key=itemgetter(0))[0]
    minx = min(arr, key=itemgetter(0))[0]

    (fx, fy) = arr[-2]
    (lx, ly) = arr[1]

    first=extrapolate(fx, fy, lx, ly, minx)
    last=extrapolate(fx, fy, lx, ly, maxx) #extrapolate(lx, ly, fx, fy,maxx)    
    return [first, last]

def eyebrowheight(arr):
    maxx = max(arr, key=itemgetter(1))[1]
    minx = min(arr, key=itemgetter(1))[1]
    return maxx-minx


def addthickeyebrows(d, face_landmarks):
    eyel = niceeyebrow(face_landmarks['left_eyebrow'])
    eyer = niceeyebrow(face_landmarks['right_eyebrow'])
    eyehr = eyebrowheight(face_landmarks['left_eyebrow'])
    eyehl = eyebrowheight(face_landmarks['left_eyebrow'])

    d.line(eyel, fill=(0, 0, 0, 255), width=eyehl)
    d.line(eyer, fill=(0, 0, 0, 255), width=eyehr)

def addprettyeyebrows(d, face_landmarks):
    d.line(face_landmarks['left_eyebrow'], fill=(68, 54, 39, 150), width=8)
    d.line(face_landmarks['right_eyebrow'], fill=(68, 54, 39, 150), width=8)

def addgoatee(d, face_landmarks):
    arr = face_landmarks['chin'][7:10]
        
    (lx, ly) = arr[0]
    (mx, my) = arr[1]
    (rx, ry) = arr[2]
    dx = lx-rx
    arr.append((mx, my-dx))

    d.polygon(arr, fill=(0, 0, 0, 200))

def lipstickcolor():
    rnd = randint(0,4)
    if rnd==0: # red
        return (150, 0, 0, 128)
    elif rnd==1: # purple
        return (128, 0, 128, 128) 
    elif rnd==2: # blue
        return (0, 0, 150, 128)
    elif rnd==3: # black
        return (10, 10, 10, 128)
    elif rnd==4: # green
        return (0, 150, 0, 128)


def makeupify(image):
    image = resize_image(image, 2)

    # Find all facial features in all the faces in the image
    if not image.mode == 'RGB':
        image = image.convert('RGB')
    face_landmarks_list = face_recognition.face_landmarks(np.array(image))
    
    if not face_landmarks_list:
        return None

    for face_landmarks in face_landmarks_list:
        d = ImageDraw.Draw(image, 'RGBA')

        # Make the eyebrows into a nightmare
        rnd = random() 
        if rnd > 0.6:
            addprettyeyebrows(d, face_landmarks)
        else:
            addthickeyebrows(d, face_landmarks)
        
        # Gloss the lips
        clr=lipstickcolor()
        d.polygon(face_landmarks['top_lip'], fill=clr)
        d.polygon(face_landmarks['bottom_lip'], fill=clr)
        d.line(face_landmarks['top_lip'], fill=clr, width=1)
        d.line(face_landmarks['bottom_lip'], fill=clr, width=1)

        # Sparkle the eyes
        d.polygon(face_landmarks['left_eye'], fill=(255, 255, 255, 30))
        d.polygon(face_landmarks['right_eye'], fill=(255, 255, 255, 30))

        # Apply some eyeliner
        d.line(face_landmarks['left_eye'] + [face_landmarks['left_eye'][0]], fill=(0, 0, 0, 110), width=4)
        d.line(face_landmarks['right_eye'] + [face_landmarks['right_eye'][0]], fill=(0, 0, 0, 110), width=4)

        # Awesome goatee
        if random() > 0.5:
            addgoatee(d, face_landmarks)
        

    image = resize_image(image, 0.5)
    bytes = BytesIO()
    image.save(bytes, 'JPEG')
    bytes.seek(0)
    return bytes


# instantiate Slack client
slack_client = SlackClient(SLACK_BOT_TOKEN)
# bot's user ID in Slack: value is assigned after the bot starts up
bot_id = None

# constants
RTM_READ_DELAY = 1 # 1 second delay between reading from RTM
EXAMPLE_COMMAND = "do"
MENTION_REGEX = "^<@(|[WU].+?)>(.*)"

def parse_events(slack_events):
    for event in slack_events:
        if not "type" in event or not "subtype" in event:
            continue

        if event["type"] == "message" and event["subtype"] == "file_share":
            if "user" in event and event["user"] == bot_id:
                continue

            file_info = slack_client.api_call(
                "files.info",
                file=event["file"]["id"],
            )
            headers = {}
            headers["Authorization"] = 'Bearer ' + SLACK_BOT_TOKEN
            response = requests.get(
                file_info["file"]["url_private_download"],
                headers=headers
            )

            if not response.ok:
                print(response)
                continue

            img = Image.open(BytesIO(response.content))

            makeup = makeupify(img)

            if not makeup:
                continue

            res = slack_client.api_call(
                "files.upload",
                channels=event["channel"],
                file=(event["file"]["id"] + '.jpg', makeup, 'image/jpeg'),
                title="Beautiful!"
            )

            if "ok" in res and not res["ok"]:
                print(res)


if __name__ == "__main__":
    if slack_client.rtm_connect(with_team_state=False):
        print("Bot connected and running!")
        # Read bot's user ID by calling Web API method `auth.test`
        bot_id = slack_client.api_call("auth.test")["user_id"]
        while True:
            parse_events(slack_client.rtm_read())
            time.sleep(RTM_READ_DELAY)
    else:
        print("Connection failed. Exception traceback printed above.")

