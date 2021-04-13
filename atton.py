#!/usr/bin/env python

from atton_config import atton_config
import re
import sys
import random
import irc.bot
import requests
import datetime
import time
import threading

def main():
    config = atton_config('config.yaml')
    bot = AttonRand(config['username'], config['client_id'], config['token'], config['channel'])
    try:
        threading.Thread(target=bot.start, daemon=True).start()
        loop(bot)
    except:
        print()

class AttonRand(irc.bot.SingleServerIRCBot):
    
    def __init__(self, username, client_id, token, channel):
        self.retry = 3
        self.update = 60
        self.username = username
        self.client_id = client_id
        self.token = token
        self.channel = channel
        self.channel_id = self.getUserInfo(channel)['users'][0]['_id']
        self.spam = "@" + self.channel + " How about a game of pazaak, Republic Senate rules? :)"
        server = 'irc.chat.twitch.tv'
        port = 6667
        print('Connecting to ' + server + ' on port ' + str(port) + '...')
        irc.bot.SingleServerIRCBot.__init__(self, [(server, port, 'oauth:'+token)], username, username)
    
    def getStreamInfo(self):
        url = 'https://api.twitch.tv/kraken/streams/' + self.channel_id
        headers = {'Client-ID': self.client_id, 'Accept': 'application/vnd.twitchtv.v5+json',  'Authorization': 'OAuth ' + self.token}
        tries = 0
        out = None
        while tries < self.retry:
            r = requests.get(url, headers=headers)
            if r.status_code == 200:
                out = r.json()
                break
            else:
                tries += 1
        return out
    
    def getUserInfo(self, user):
        url = 'https://api.twitch.tv/kraken/users?login=' + self.channel
        headers = {'Client-ID': self.client_id, 'Accept': 'application/vnd.twitchtv.v5+json'}
        tries = 0
        out = None
        while tries < self.retry:
            r = requests.get(url, headers=headers)
            if r.status_code == 200:
                out = r.json()
                break
            else:
                tries += 1
        return out

    def isLive(self):
        r = self.getStreamInfo()
        if r and r['stream']:
            if r['stream']['stream_type'] == 'live':
                return True
            else:
                return False
        else:
            return False

    def on_pubmsg(self, c, e):
        for tag in e.tags:
            if tag['key'] == "display-name":
                name = tag['value']
            if tag['key'] == "user-id":
                userid = tag['value']
            if tag['key'] == "tmi-sent-ts":
                time = tag['value']
        if e.arguments[0][:1] == '!':
            cmd = e.arguments[0].split(' ')[0][1:]
        if e.arguments[0].lower().find(self.username.lower()) != -1:
            print(datetime.datetime.now().strftime('%X-%x') + " " + name + ": " + e.arguments[0])

    def on_welcome(self, c, e):
        print(datetime.datetime.now().strftime('%X-%x') + ': ' + 'Joining #' + self.channel)
        c.cap('REQ', ':twitch.tv/membership')
        c.cap('REQ', ':twitch.tv/tags')
        c.cap('REQ', ':twitch.tv/commands')
        c.join('#' + self.channel)
    
    def on_join(self, c, e):
        print(datetime.datetime.now().strftime('%X-%x') + ': ' + 'Joined #' + self.channel)
    
def loop(bot):
    wasStreaming = True
    while True:
        if bot.isLive():
            if not wasStreaming:
                print(datetime.datetime.now().strftime('%X-%x') + ': ' + bot.channel + " just went live!")
                delay = random.randrange(120, 300)
                print(datetime.datetime.now().strftime('%X-%x') + ': ' + "Waiting " + str(delay) + " seconds to post...")
                time.sleep(delay)
                message = bot.spam
                print(datetime.datetime.now().strftime('%X-%x') + ': ' + message)
                bot.connection.privmsg('#' + bot.channel, message)
            wasStreaming = True
        else:
            if wasStreaming:
                print(datetime.datetime.now().strftime('%X-%x') + ': ' + bot.channel + " just went offline.")
            wasStreaming = False
        time.sleep(bot.update)


if __name__ == "__main__":
    main()