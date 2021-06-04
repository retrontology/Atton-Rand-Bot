#!/usr/bin/env python

from threading import Thread
import retroBot
import retroBot.config
import random
import datetime
import time


class AttonRand(retroBot.retroBot):
    
    def __init__(self, config):
        self.config = config
        super(AttonRand, self).__init__(config['username'], config['client_id'], config['client_secret'], [config['channel']], handler=AttonHandler, webhook_host=config['webhook']['host'], webhook_port=config['webhook']['port'], ssl_cert=config['webhook']['ssl_cert'], ssl_key=config['webhook']['ssl_key'])

class AttonHandler(retroBot.channelHandler):

    def __init__(self, channel, parent):
        super(AttonHandler, self).__init__(channel, parent)
        self.user_id = self.get_user_id(channel)
        self.message = "@" + channel + " How about a game of !pazaak, Republic Senate rules? :)"
        self.init_cooldowns()
        self.get_live()
        self.webhook_stream_changed_subscribe()

    def init_cooldowns(self):
        self.cooldown = {}
        self.last_used = {}
        self.cooldown['pazaak'] = 10*60
        self.last_used['pazaak'] = datetime.datetime.fromtimestamp(0)

    def on_pubmsg(self, c, e):
        msg = retroBot.message(e)
        if msg.content[:1] == '!':
            cmd = msg.content.split(' ')[0][1:]
            if cmd.lower() == 'pazaak':
                if msg.username.lower() == self.channel:
                    self.send_message(f'@{msg.username} !pazaak these nuts in your mouth biiiiiitch :)')
                    self.logger.info('GOTTEEM!!!')
                elif (datetime.datetime.now() - self.last_used['pazaak']).total_seconds() > self.cooldown['pazaak']:
                    self.logger.info(f'baiting {msg.username}...')
                    self.last_used['pazaak'] = datetime.datetime.now()
                    self.send_message(f'Sorry @{msg.username}, only the channel owner can play !pazaak')
        if msg.content.lower().find(self.username.lower()) != -1:
            self.logger.info(f'{msg.username}: {msg.content}')
    
    def callback_stream_gone_live(self, uuid, data):
        Thread(target=self.spam, daemon=True).start()

    def spam(self):
        time.sleep(random.randrange(60, 180))
        self.send_message(self.message)