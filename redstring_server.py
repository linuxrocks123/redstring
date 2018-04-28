#! /usr/bin/env python2

import socket
import sys
from select import select

from ontask_messages import *

#Data structures
sockets_for_group = {} # {"groupname" : set([socket1,socket2,...]),...}
group_for_socket = {} # {socket1 : "groupname",socket2 : "groupname"}
nick_for_socket = {} # {socket1 : "nick",...}

#New client
def add_socket(socket,nick,group):
    if group in sockets_for_group:
        sockets_for_group[group].add(socket)
    else:
        sockets_for_group[group] = set([socket])
    group_for_socket[socket] = group
    nick_for_socket[socket] = nick

#Grim Reaper
def reap(damned):
    group = group_for_socket[damned]
    set_to_reap = sockets_for_group[group]
    set_to_reap.remove(damned)
    del group_for_socket[damned]
    del nick_for_socket[damned]

    #Send updated roster
    for remaining_member in set_to_reap:
        try:
            remaining_member.write(OnTask_Message("ROSTER",nickslist_for_group(group)).get_message_string())
            remaining_member.flush()
        except:
            reap(remaining_member)

#Get list of nicks in group
def nickslist_for_group(group):
    to_return = []
    for socket in sockets_for_group[group]:
        to_return.append(nick_for_socket[socket])
    return "\n".join(to_return)

#Create Listener
listener = socket.socket()
listener.bind(('',int(sys.argv[1])))
listener.listen(5)

#Add listener so we can just select on group_for_socket.keys()
group_for_socket[listener] = ""

while True:
    retvals = select(group_for_socket.keys(),(),())
    for socket in retvals[0]:
        group_name = group_for_socket[socket]
        if group_name=="": #we are the listener
            new_socket_ = socket.accept()[0]
            new_socket = new_socket_.makefile()
            try:
                identity_notice = OnTask_Message.message_from_socket(new_socket)
                if identity_notice.cmd_id!="HELLO":
                    new_socket.close()
                    continue

                #Get our nick and group, add us to data structures
                lines = identity_notice.body.splitlines()
                nick = lines[0]
                group = lines[1]
                add_socket(new_socket,nick,group)
                
                #Send roster message to all group members
                for member in set(sockets_for_group[group]):
                    try:
                        member.write(OnTask_Message("ROSTER",nickslist_for_group(group)).get_message_string())
                        member.flush()
                    except:
                        reap(member)
            except:
                pass
        else:
            #Get the message
            try:
                message = OnTask_Message.message_from_socket(socket)
            except:
                reap(socket)
                continue

            #Prefix chat message with nick of sender
            if message.cmd_id=="CHAT":
                message.body = nick_for_socket[socket]+": "+message.body

            #Send message to all other group members
            for member in set(sockets_for_group[group_for_socket[socket]]):
                if member!=socket:
                    try:
                        member.write(message.get_message_string())
                        member.flush()
                    except:
                        reap(member)
