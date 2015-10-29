#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Created by Johann Fridriksson by crudely merging/remixing example codes from
# both irc (https://pypi.python.org/pypi/irc) and xmpppy (http://xmpppy.sourceforge.net/)

import argparse
import ConfigParser
import os
import xmpp
import irc.bot
import irc.strings
import irc
from irc.client import ip_numstr_to_quad, ip_quad_to_numstr
import time, os, sys, select
import ssl
import threading
import bingtranslate

class XMPPBot:
    def __init__(self,jabber,remotejid, translate=False, translate_from="en", translate_to="da"):
        self.jabber = jabber
        self.remotejid = remotejid
        self.ircbot = None
        self.translate = translate
        self.translate_from = translate_from
        self.translate_to = translate_to

    def set_ircbot(self, ircbot):
        self.ircbot = ircbot

    def register_handlers(self):
        self.jabber.RegisterHandler("message",self.xmpp_message)

    def xmpp_message(self, con, event):
        type = event.getType()
        fromjid = event.getFrom().getStripped()
        body = event.getBody()
        if type in ["message", "chat", None] and fromjid == self.remotejid and body:
            #sys.stdout.write(body + "\n")
            if self.ircbot != None:
                if self.translate:
                    translated = bingtranslate.translate(body, self.translate_from, self.translate_to)
                    self.ircbot.send_message("%s [%s]"%(translated.decode("utf8"), body))
                else:
                    self.ircbot.send_message(body)

    def send_message(self, message):
        m = xmpp.protocol.Message(to=self.remotejid,body=message,typ="chat")
        self.jabber.send(m)

    def xmpp_connect(self, password):
        con=self.jabber.connect()
        if not con:
            sys.stderr.write("could not connect!\n")
            return False
        #sys.stderr.write("connected with %s\n"%con)
        auth=self.jabber.auth(jid.getNode(),password,resource=jid.getResource())
        if not auth:
            sys.stderr.write("could not authenticate!\n")
            return False
        #sys.stderr.write("authenticated using %s\n"%auth)
        self.register_handlers()
        return con



class IRCBot(irc.bot.SingleServerIRCBot):
    def __init__(self, channel, nickname, server, port, use_ssl=False, translate=False, translate_from="da", translate_to="en"):
        if use_ssl:
            ssl_factory = irc.connection.Factory(wrapper=ssl.wrap_socket)
            irc.bot.SingleServerIRCBot.__init__(self, [(server, port)], nickname, nickname, connect_factory=ssl_factory)
        else:
             irc.bot.SingleServerIRCBot.__init__(self, [(server, port)], nickname, nickname)
        self.channel = channel
        self.xmppbot = None
        self.debug = True
        self.translate = translate
        self.translate_from = translate_from
        self.translate_to = translate_to

    def send_message(self, message):
        self.connection.privmsg(self.channel, message)

    def set_xmppbot(self, xmppbot):
        self.xmppbot = xmppbot

    def on_nicknameinuse(self, c, e):
        c.nick(c.get_nickname() + "_")

    def on_welcome(self, c, e):
        c.join(self.channel)

    def on_privmsg(self, c, e):
        nick = e.source.nick
        c.notice(nick, "I am an XMPP relay bot. Private messages have not yet been implemented.")

    def on_pubmsg(self, c, e):
        a = e.arguments[0]
        nick = e.source.nick
        if self.xmppbot != None:
            if self.translate:
                translated = bingtranslate.translate(a, self.translate_from, self.translate_to)
                self.xmppbot.send_message("<%s> %s [%s]"%(nick, translated.decode("utf8"), a))
            else:
                self.xmppbot.send_message("<%s> %s"%(nick, a))


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        prog=sys.argv[0],
        description="XMPP to IRC relay"
    )
    parser.add_argument("-c", "--config", dest="file", help="Configuration file", default="~/.xmppirc.conf")


    args = parser.parse_args(sys.argv[1:])


    config = ConfigParser.ConfigParser()
    config.read(os.path.expanduser(args.file))

    #############
    # Intialize and connect via XMPP
    jid = xmpp.protocol.JID(
        config.get("xmpp", "my_jid"),
    )
    cl = xmpp.Client(jid.getDomain(), debug=[])

    xmppBot = XMPPBot(
        cl,
        config.get("xmpp", "remote_jid"),
        config.getboolean("xmpp", "translate"),
        config.get("xmpp", "translate_from"),
        config.get("xmpp", "translate_to")        
    )
    if not xmppBot.xmpp_connect(config.get("xmpp", "password")):
        sys.stderr.write("Could not connect to XMPP server!\n")
        sys.exit(1)

    cl.sendInitPresence(requestRoster=0)
    #############

    
    #############
    # Initialize and connect via IRC
    #ircBot = IRCBot(irc_channel, irc_nick, irc_server, irc_port)
    ircBot = IRCBot(
        config.get("irc", "channel"),
        config.get("irc", "nick"),
        config.get("irc", "server"),
        config.getint("irc", "port"),
        config.getboolean("irc", "ssl"),
        config.getboolean("irc", "translate"),
        config.get("irc", "translate_from"),
        config.get("irc", "translate_to")
    )
    ircThread = threading.Thread(target=ircBot.start)
    ircThread.setDaemon(True)
    ircThread.start()
    #############

    ircBot.set_xmppbot(xmppBot)
    xmppBot.set_ircbot(ircBot)


    socketlist = {cl.Connection._sock : "xmpp"}
    while True:
        (i, o, e) = select.select(socketlist.keys(), [], [], 1)
        for each in i:
            if socketlist[each] == "xmpp":
                cl.Process(1)
            else:
                raise Exception("Unknown socket type: %s" % repr(socketlist[each]))
    ircThread.join()
