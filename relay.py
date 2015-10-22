#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Created by Johann Fridriksson by crudely merging/remixing example codes from
# both irc (https://pypi.python.org/pypi/irc) and xmpppy (http://xmpppy.sourceforge.net/)

import xmpp
import irc.bot
import irc.strings
import irc
from irc.client import ip_numstr_to_quad, ip_quad_to_numstr
import time, os, sys, select
import ssl
import threading

class XMPPBot:
    def __init__(self,jabber,remotejid):
        self.jabber = jabber
        self.remotejid = remotejid
        self.ircbot = None

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
    def __init__(self, channel, nickname, server, port=9999):
        ssl_factory = irc.connection.Factory(wrapper=ssl.wrap_socket)
        irc.bot.SingleServerIRCBot.__init__(self, [(server, port)], nickname, nickname, connect_factory=ssl_factory)
        self.channel = channel
        self.xmppbot = None
        self.debug = True

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
            self.xmppbot.send_message("<%s> %s"%(nick, a))

if __name__ == "__main__":
    if len(sys.argv) < 6:
        sys.stderr.write("Usage: %s <ircserver:port> <channel> <nick> <MyJabberID:passwd> <RemoteJabberID>\n"%sys.argv[0])
        exit(1)

    serversplit = sys.argv[1].split(":")
    irc_server = serversplit[0]
    irc_port = int(serversplit[1])
    irc_channel = sys.argv[2]
    irc_nick = sys.argv[3]
    jid_split = sys.argv[4].split(":")
    my_jid = jid_split[0]
    my_jid_passwd = jid_split[1]
    tojid_string = sys.argv[5]

    #############
    # Intialize and connect via XMPP
    jid = xmpp.protocol.JID(my_jid)
    cl = xmpp.Client(jid.getDomain(), debug=[])

    xmppBot = XMPPBot(cl, tojid_string)
    if not xmppBot.xmpp_connect(my_jid_passwd):
        sys.stderr.write("Could not connect to XMPP server!\n")
        sys.exit(1)

    cl.sendInitPresence(requestRoster=0)
    #############

    
    #############
    # Initialize and connect via IRC
    ircBot = IRCBot(irc_channel, irc_nick, irc_server, irc_port)
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
