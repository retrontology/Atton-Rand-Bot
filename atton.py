#!/usr/bin/env python

from webhook_ssl import proxy_request_handler
from twitchAPI.twitch import Twitch
from twitchAPI.webhook import TwitchWebHook
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.types import AuthScope
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
import pickle
import os


class AttonRand(irc.bot.SingleServerIRCBot):
    
    def __init__(self, config):
        self.logger = logging.getLogger('AttonRand.Bot')
        self.config = config
        self.retry = 3
        self.init_cooldowns()
        self.username = config['username']
        self.client_id = config['client_id']
        self.client_secret = config['client_secret']
        self.channel = config['channel']
        self.twitch_setup()
        self.get_oauth_token()
        self.user_id = self.get_user_id(self.channel)
        self.get_live()
        self.setup_ssl_reverse_proxy()
        self.webhook_setup()
        self.webhook_subscribe()
        self.message = "@" + self.channel + " How about a game of !pazaak, Republic Senate rules? :)"
        self.irc_server = 'irc.chat.twitch.tv'
        self.irc_port = 6667
        self.logger.info(f'Connecting to {self.irc_server} on port {self.irc_port}...')
        irc.bot.SingleServerIRCBot.__init__(self, [(self.irc_server, self.irc_port, 'oauth:'+self.token)], self.username, self.username)

    def init_cooldowns(self):
        self.cooldown = {}
        self.last_used = {}
        self.cooldown['pazaak'] = 10*60
        self.last_used['pazaak'] = datetime.datetime.fromtimestamp(0)

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
            if cmd.lower() == 'pazaak':
                if name.lower() == self.channel:
                    self.connection.privmsg('#' + self.channel, f'@{name} !pazaak these nuts in your mouth biiiiiitch :)')
                    self.logger.info('GOTTEEM!!!')
                elif (datetime.datetime.now() - self.last_used['pazaak']).total_seconds() > self.cooldown['pazaak']:
                    self.last_used['pazaak'] = datetime.datetime.now()
                    self.connection.privmsg('#' + self.channel, f'Sorry @{name}, only the channel owner can play !pazaak')
                    self.logger.info(f'baiting {name}...')
        if e.arguments[0].lower().find(self.username.lower()) != -1:
            self.logger.info(f'{name}: {e.arguments[0]}')

    def on_welcome(self, c, e):
        self.logger.info(f'Joining #{self.channel.lower()}...')
        c.cap('REQ', ':twitch.tv/membership')
        c.cap('REQ', ':twitch.tv/tags')
        c.cap('REQ', ':twitch.tv/commands')
        c.join('#' + self.channel.lower())
    
    def on_join(self, c, e):
        self.logger.info(f'Joined {e.target}!')

    def get_user_id(self, channel):
        user_info = self.twitch.get_users(logins=[channel.lower()])
        return user_info['data'][0]['id']

    def get_live(self):
        data = self.twitch.get_streams(user_id=self.user_id)
        if not data['data']:
            self.live = False
            self.logger.info(f'{self.channel} is not live')
        elif data['data'][0]['type'] == 'live':
            self.live = True
            self.logger.info(f'{self.channel} is live!')
        else:
            self.live = False
        return self.live
    
    def twitch_setup(self):
        self.logger.info(f'Setting up Twitch API client...')
        self.twitch = Twitch(self.client_id, self.client_secret)
        self.twitch.user_auth_refresh_callback = self.oauth_user_refresh
        self.twitch.authenticate_app([])
        self.logger.info(f'Twitch API client set up!')

    def setup_ssl_reverse_proxy(self):
        self.logger.info(f'Setting up SSL reverse proxy for webhook...')
        handler = partial(proxy_request_handler, self.config['webhook']['port'])
        if 'local' in self.config['webhook'] and self.config['webhook']['local'] != '':
            ip = self.config['webhook']['local']
        else:
            ip = self.config['webhook']['host']
        self.httpd = http.server.HTTPServer((ip, self.config['webhook']['ssl_port']), handler)
        self.httpd.socket = ssl.wrap_socket(self.httpd.socket, certfile=self.config['webhook']['ssl_cert'], server_side=True)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.logger.info(f'SSL reverse proxy set up!')
    
    def webhook_setup(self):
        self.logger.info(f'Setting up Twitch webhook...')
        self.webhook = TwitchWebHook('https://' + self.config['webhook']['host'] + ":" + str(self.config['webhook']['ssl_port']), self.client_id, self.config['webhook']['port'])
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
                self.spam()
            else:
                self.live = True
        else:
            self.live = False
            self.logger.info(f'{self.channel} has gone offline')

    def get_oauth_token(self):
        tokens = self.load_oauth_token()
        target_scope = [AuthScope.CHAT_EDIT, AuthScope.CHAT_READ]
        if tokens == None:
            auth = UserAuthenticator(self.twitch, target_scope, force_verify=False)
            self.token, self.refresh_token = auth.authenticate()
            self.save_oauth_token()
        else:
            self.token = tokens[0]
            self.refresh_token = tokens[1]
        self.twitch.set_user_authentication(self.token, target_scope, self.refresh_token)

    def save_oauth_token(self):
        pickle_file = self.get_oauth_file()
        with open(pickle_file, 'wb') as f:
            pickle.dump((self.token, self.refresh_token), f)
        self.logger.debug(f'OAuth Token has been saved')

    def load_oauth_token(self):
        pickle_file = self.get_oauth_file()
        if os.path.exists(pickle_file):
            with open(pickle_file, 'rb') as f:
                out = pickle.load(f)
            self.logger.debug(f'OAuth Token has been loaded')
            return out
        else: return None

    def get_oauth_file(self):
        pickle_dir = os.path.join(os.path.dirname(__file__), 'oauth')
        if not os.path.exists(pickle_dir): os.mkdir(pickle_dir)
        pickle = os.path.join(pickle_dir, f'{self.username}_oauth.pickle')
        return pickle
    
    def oauth_user_refresh(self, token, refresh_token):
        self.logger.debug(f'Refreshing OAuth Token')
        self.token = token
        self.refresh_token = refresh_token
        irc.bot.SingleServerIRCBot.__init__(self, [(self.irc_server, self.irc_port, 'oauth:'+self.token)], self.username, self.username)
        self._connect()
        self.save_oauth_token()
    
    def spam(self):
        time.sleep(random.randrange(60, 180))
        self.logger.info(self.message)
        self.connection.privmsg('#' + self.channel, self.message)