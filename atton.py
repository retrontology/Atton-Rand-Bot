#!/usr/bin/env python

from webhook_ssl import proxy_request_handler
from twitchAPI.twitch import Twitch
from twitchAPI.webhook import TwitchWebHook
from functools import partial
import re
import sys
import random
import irc.bot
import requests
import datetime
import time
import logging
import threading
import http
import ssl


class AttonRand(irc.bot.SingleServerIRCBot):
    
    def __init__(self, config):
        self.logger = logging.getLogger('AttonRand.Bot')
        self.config = config
        self.retry = 3
        self.username = config['username']
        self.client_id = config['client_id']
        self.client_secret = config['client_secret']
        self.channel = config['channel']
        self.twitch_setup()
        self.token =
        self.user_id = self.get_user_id(self.channel)
        self.get_live()
        self.setup_ssl_reverse_proxy()
        self.webhook_setup()
        self.webhook_subscribe()
        self.message = "@" + self.channel + " How about a game of pazaak, Republic Senate rules? :)"
        self.irc_server = 'irc.chat.twitch.tv'
        self.irc_port = 6667
        self.logger.info(f'Connecting to {self.irc_server} on port {self.irc_port}...')
        irc.bot.SingleServerIRCBot.__init__(self, [(self.irc_server, self.irc_port, 'oauth:'+self.token)], self.username, self.username)

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
            self.logger.info(f'{name}: {e.arguments[0]}')

    def on_welcome(self, c, e):
        self.logger.info(f'Joining #{self.channel}...')
        c.cap('REQ', ':twitch.tv/membership')
        c.cap('REQ', ':twitch.tv/tags')
        c.cap('REQ', ':twitch.tv/commands')
        c.join('#' + self.channel)
    
    def on_join(self, c, e):
        self.logger.info(f'Joined #{self.channel}!')
    
    def get_user_id(self, channel):
        user_info = self.twitch.get_users(logins=[channel])
        return user_info['data'][0]['id']

    def get_live(self):
        data = self.twitch.get_streams(user_id=self.user_id)
        if not data['data']:
            self.live = False
        elif data['data'][0]['type'] == 'live':
            self.live = True
        else:
            self.live = False
        return self.live
    
    def twitch_setup(self):
        self.logger.info(f'Setting up Twitch API client...')
        self.twitch = Twitch(self.client_id, self.client_secret)
        self.twitch.authenticate_app([])
        self.logger.info(f'Twitch API client set up!')

    def setup_ssl_reverse_proxy(self):
        self.logger.info(f'Setting up SSL reverse proxy for webhook...')
        handler = partial(proxy_request_handler, self.config['webhook']['port'])
        self.httpd = http.server.HTTPServer((self.config['webhook']['host'], self.config['webhook']['ssl_port']), handler)
        self.httpd.socket = ssl.wrap_socket(self.httpd.socket, certfile=self.config['webhook']['ssl_cert'], server_side=True)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.logger.info(f'SSL reverse proxy set up!')
    
    def webhook_setup(self):
        self.logger.info(f'Setting up Twitch webhook...')
        self.webhook = TwitchWebHook('https://' + self.config['host'] + ":" + str(self.config['webhook']['ssl_port']), self.client_id, self.config['webhook']['port'])
        self.webhook.authenticate(self.twitch) 
        self.webhook.start()
        self.logger.info(f'Twitch webhook set up!')
    
    def webhook_unsubscribe(self):
        if self.webhook_uuid:
            success = self.webhook.unsubscribe(self.webhook_uuid)
            if success:
                self.webhook_uuid = ''
                self.logger.info(f'Unsubscribed from webhook for {self.channel}')
            return success

    def webhook_subscribe(self):
        success, uuid = self.webhook.subscribe_stream_changed(self.user_id, self.callback_stream_changed)
        if success:
            self.webhook_uuid = uuid
            self.logger.info(f'Subscribed to webhook for {self.channel}')
        else:
            self.webhook_uuid = None
        return success
    
    def callback_stream_changed(self, uuid, data):
        self.logger.info(f'Received webhook callback for {self.channel}')
        if data['type'] == 'live':
            if not self.live:
                self.live = True
                self.logger.info(f'{self.channel} has gone live!')
                threading.Thread(target=self.spam, daemon=True).start()
            else:
                self.live = True
        else:
            self.live = False
            self.logger.info(f'{self.channel} has gone offline')
    
    def spam(self):
        time.sleep(random.randrange(60, 180))
        self.logger.info(self.message)
        self.connection.privmsg('#' + self.channel, self.message)
    
    def __del__(self):
        self.logger.info(f'Shutting down')
        self.webhook_unsubscribe()
        self.webhook.stop()
        self.httpd.shutdown()
        self.httpd.socket.close()