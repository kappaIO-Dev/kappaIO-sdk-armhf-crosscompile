#! /usr/bin/python3.2
"""An RFC 2821 smtp proxy.

Usage: %(program)s [options] [localhost:localport [remotehost:remoteport]]

Options:

    --nosetuid
    -n
        This program generally tries to setuid `nobody', unless this flag is
        set.  The setuid call will fail if this program is not run as root (in
        which case, use this flag).

    --version
    -V
        Print the version number and exit.

    --class classname
    -c classname
        Use `classname' as the concrete SMTP proxy class.  Uses `PureProxy' by
        default.

    --debug
    -d
        Turn on debugging prints.

    --help
    -h
        Print this message and exit.

Version: %(__version__)s

If localhost is not given then `localhost' is used, and if localport is not
given then 8025 is used.  If remotehost is not given then `localhost' is used,
and if remoteport is not given, then 25 is used.
"""


# Overview:
#
# This file implements the minimal SMTP protocol as defined in RFC 821.  It
# has a hierarchy of classes which implement the backend functionality for the
# smtpd.  A number of classes are provided:
#
#   SMTPServer - the base class for the backend.  Raises NotImplementedError
#   if you try to use it.
#
#   DebuggingServer - simply prints each message it receives on stdout.
#
#   PureProxy - Proxies all messages to a real smtpd which does final
#   delivery.  One known problem with this class is that it doesn't handle
#   SMTP errors from the backend server at all.  This should be fixed
#   (contributions are welcome!).
#
#   MailmanProxy - An experimental hack to work with GNU Mailman
#   <www.list.org>.  Using this server as your real incoming smtpd, your
#   mailhost will automatically recognize and accept mail destined to Mailman
#   lists when those lists are created.  Every message not destined for a list
#   gets forwarded to a real backend smtpd, as with PureProxy.  Again, errors
#   are not handled correctly yet.
#
#
# Author: Barry Warsaw <barry@python.org>
#
# TODO:
#
# - support mailbox delivery
# - alias files
# - ESMTP
# - handle error codes from the backend smtpd

import sys
import os
import errno
import getopt
import time
import socket
import asyncore
import asynchat
from warnings import warn

__all__ = ["SMTPServer","DebuggingServer","PureProxy","MailmanProxy"]

program = sys.argv[0]
__version__ = 'Python SMTP proxy version 0.2'


class Devnull:
    def write(self, msg): pass
    def flush(self): pass


DEBUGSTREAM = Devnull()
NEWLINE = '\n'
EMPTYSTRING = ''
COMMASPACE = ', '



def usage(code, msg=''):
    print(__doc__ % globals(), file=sys.stderr)
    if msg:
        print(msg, file=sys.stderr)
    sys.exit(code)



class SMTPChannel(asynchat.async_chat):
    COMMAND = 0
    DATA = 1

    data_size_limit = 33554432
    command_size_limit = 512

    def __init__(self, server, conn, addr):
        asynchat.async_chat.__init__(self, conn)
        self.smtp_server = server
        self.conn = conn
        self.addr = addr
        self.received_lines = []
        self.smtp_state = self.COMMAND
        self.seen_greeting = ''
        self.mailfrom = None
        self.rcpttos = []
        self.received_data = ''
        self.fqdn = socket.getfqdn()
        self.num_bytes = 0
        try:
            self.peer = conn.getpeername()
        except socket.error as err:
            # a race condition  may occur if the other end is closing
            # before we can get the peername
            self.close()
            if err.args[0] != errno.ENOTCONN:
                raise
            return
        print('Peer:', repr(self.peer), file=DEBUGSTREAM)
        self.push('220 %s %s' % (self.fqdn, __version__))
        self.set_terminator(b'\r\n')

    # properties for backwards-compatibility
    @property
    def __server(self):
        warn("Access to __server attribute on SMTPChannel is deprecated, "
            "use 'smtp_server' instead", PendingDeprecationWarning, 2)
        return self.smtp_server
    @__server.setter
    def __server(self, value):
        warn("Setting __server attribute on SMTPChannel is deprecated, "
            "set 'smtp_server' instead", PendingDeprecationWarning, 2)
        self.smtp_server = value

    @property
    def __line(self):
        warn("Access to __line attribute on SMTPChannel is deprecated, "
            "use 'received_lines' instead", PendingDeprecationWarning, 2)
        return self.received_lines
    @__line.setter
    def __line(self, value):
        warn("Setting __line attribute on SMTPChannel is deprecated, "
            "set 'received_lines' instead", PendingDeprecationWarning, 2)
        self.received_lines = value

    @property
    def __state(self):
        warn("Access to __state attribute on SMTPChannel is deprecated, "
            "use 'smtp_state' instead", PendingDeprecationWarning, 2)
        return self.smtp_state
    @__state.setter
    def __state(self, value):
        warn("Setting __state attribute on SMTPChannel is deprecated, "
            "set 'smtp_state' instead", PendingDeprecationWarning, 2)
        self.smtp_state = value

    @property
    def __greeting(self):
        warn("Access to __greeting attribute on SMTPChannel is deprecated, "
            "use 'seen_greeting' instead", PendingDeprecationWarning, 2)
        return self.seen_greeting
    @__greeting.setter
    def __greeting(self, value):
        warn("Setting __greeting attribute on SMTPChannel is deprecated, "
            "set 'seen_greeting' instead", PendingDeprecationWarning, 2)
        self.seen_greeting = value

    @property
    def __mailfrom(self):
        warn("Access to __mailfrom attribute on SMTPChannel is deprecated, "
            "use 'mailfrom' instead", PendingDeprecationWarning, 2)
        return self.mailfrom
    @__mailfrom.setter
    def __mailfrom(self, value):
        warn("Setting __mailfrom attribute on SMTPChannel is deprecated, "
            "set 'mailfrom' instead", PendingDeprecationWarning, 2)
        self.mailfrom = value

    @property
    def __rcpttos(self):
        warn("Access to __rcpttos attribute on SMTPChannel is deprecated, "
            "use 'rcpttos' instead", PendingDeprecationWarning, 2)
        return self.rcpttos
    @__rcpttos.setter
    def __rcpttos(self, value):
        warn("Setting __rcpttos attribute on SMTPChannel is deprecated, "
            "set 'rcpttos' instead", PendingDeprecationWarning, 2)
        self.rcpttos = value

    @property
    def __data(self):
        warn("Access to __data attribute on SMTPChannel is deprecated, "
            "use 'received_data' instead", PendingDeprecationWarning, 2)
        return self.received_data
    @__data.setter
    def __data(self, value):
        warn("Setting __data attribute on SMTPChannel is deprecated, "
            "set 'received_data' instead", PendingDeprecationWarning, 2)
        self.received_data = value

    @property
    def __fqdn(self):
        warn("Access to __fqdn attribute on SMTPChannel is deprecated, "
            "use 'fqdn' instead", PendingDeprecationWarning, 2)
        return self.fqdn
    @__fqdn.setter
    def __fqdn(self, value):
        warn("Setting __fqdn attribute on SMTPChannel is deprecated, "
            "set 'fqdn' instead", PendingDeprecationWarning, 2)
        self.fqdn = value

    @property
    def __peer(self):
        warn("Access to __peer attribute on SMTPChannel is deprecated, "
            "use 'peer' instead", PendingDeprecationWarning, 2)
        return self.peer
    @__peer.setter
    def __peer(self, value):
        warn("Setting __peer attribute on SMTPChannel is deprecated, "
            "set 'peer' instead", PendingDeprecationWarning, 2)
        self.peer = value

    @property
    def __conn(self):
        warn("Access to __conn attribute on SMTPChannel is deprecated, "
            "use 'conn' instead", PendingDeprecationWarning, 2)
        return self.conn
    @__conn.setter
    def __conn(self, value):
        warn("Setting __conn attribute on SMTPChannel is deprecated, "
            "set 'conn' instead", PendingDeprecationWarning, 2)
        self.conn = value

    @property
    def __addr(self):
        warn("Access to __addr attribute on SMTPChannel is deprecated, "
            "use 'addr' instead", PendingDeprecationWarning, 2)
        return self.addr
    @__addr.setter
    def __addr(self, value):
        warn("Setting __addr attribute on SMTPChannel is deprecated, "
            "set 'addr' instead", PendingDeprecationWarning, 2)
        self.addr = value

    # Overrides base class for convenience
    def push(self, msg):
        asynchat.async_chat.push(self, bytes(msg + '\r\n', 'ascii'))

    # Implementation of base class abstract method
    def collect_incoming_data(self, data):
        limit = None
        if self.smtp_state == self.COMMAND:
            limit = self.command_size_limit
        elif self.smtp_state == self.DATA:
            limit = self.data_size_limit
        if limit and self.num_bytes > limit:
            return
        elif limit:
            self.num_bytes += len(data)
        self.received_lines.append(str(data, "utf8"))

    # Implementation of base class abstract method
    def found_terminator(self):
        line = EMPTYSTRING.join(self.received_lines)
        print('Data:', repr(line), file=DEBUGSTREAM)
        self.received_lines = []
        if self.smtp_state == self.COMMAND:
            if self.num_bytes > self.command_size_limit:
                self.push('500 Error: line too long')
                self.num_bytes = 0
                return
            self.num_bytes = 0
            if not line:
                self.push('500 Error: bad syntax')
                return
            method = None
            i = line.find(' ')
            if i < 0:
                command = line.upper()
                arg = None
            else:
                command = line[:i].upper()
                arg = line[i+1:].strip()
            method = getattr(self, 'smtp_' + command, None)
            if not method:
                self.push('502 Error: command "%s" not implemented' % command)
                return
            method(arg)
            return
        else:
            if self.smtp_state != self.DATA:
                self.push('451 Internal confusion')
                self.num_bytes = 0
                return
            if self.num_bytes > self.data_size_limit:
                self.push('552 Error: Too much mail data')
                self.num_bytes = 0
                return
            # Remove extraneous carriage returns and de-transparency according
            # to RFC 821, Section 4.5.2.
            data = []
            for text in line.split('\r\n'):
                if text and text[0] == '.':
                    data.append(text[1:])
                else:
                    data.append(text)
            self.received_data = NEWLINE.join(data)
            status = self.smtp_server.process_message(self.peer,
                                                      self.mailfrom,
                                                      self.rcpttos,
                                                      self.received_data)
            self.rcpttos = []
            self.mailfrom = None
            self.smtp_state = self.COMMAND
            self.num_bytes = 0
            self.set_terminator(b'\r\n')
            if not status:
                self.push('250 Ok')
            else:
                self.push(status)

    # SMTP and ESMTP commands
    def smtp_HELO(self, arg):
        if not arg:
            self.push('501 Syntax: HELO hostname')
            return
        if self.seen_greeting:
            self.push('503 Duplicate HELO/EHLO')
        else:
            self.seen_greeting = arg
            self.push('250 %s' % self.fqdn)

    def smtp_NOOP(self, arg):
        if arg:
            self.push('501 Syntax: NOOP')
        else:
            self.push('250 Ok')

    def smtp_QUIT(self, arg):
        # args is ignored
        self.push('221 Bye')
        self.close_when_done()

    # factored
    def __getaddr(self, keyword, arg):
        address = None
        keylen = len(keyword)
        if arg[:keylen].upper() == keyword:
            address = arg[keylen:].strip()
            if not address:
                pass
            elif address[0] == '<' and address[-1] == '>' and address != '<>':
                # Addresses can be in the form <person@dom.com> but watch out
                # for null address, e.g. <>
                address = address[1:-1]
        return address

    def smtp_MAIL(self, arg):
        print('===> MAIL', arg, file=DEBUGSTREAM)
        address = self.__getaddr('FROM:', arg) if arg else None
        if not address:
            self.push('501 Syntax: MAIL FROM:<address>')
            return
        if self.mailfrom:
            self.push('503 Error: nested MAIL command')
            return
        self.mailfrom = address
        print('sender:', self.mailfrom, file=DEBUGSTREAM)
        self.push('250 Ok')

    def smtp_RCPT(self, arg):
        print('===> RCPT', arg, file=DEBUGSTREAM)
        if not self.mailfrom:
            self.push('503 Error: need MAIL command')
            return
        address = self.__getaddr('TO:', arg) if arg else None
        if not address:
            self.push('501 Syntax: RCPT TO: <address>')
            return
        self.rcpttos.append(address)
        print('recips:', self.rcpttos, file=DEBUGSTREAM)
        self.push('250 Ok')

    def smtp_RSET(self, arg):
        if arg:
            self.push('501 Syntax: RSET')
            return
        # Resets the sender, recipients, and data, but not the greeting
        self.mailfrom = None
        self.rcpttos = []
        self.received_data = ''
        self.smtp_state = self.COMMAND
        self.push('250 Ok')

    def smtp_DATA(self, arg):
        if not self.rcpttos:
            self.push('503 Error: need RCPT command')
            return
        if arg:
            self.push('501 Syntax: DATA')
            return
        self.smtp_state = self.DATA
        self.set_terminator(b'\r\n.\r\n')
        self.push('354 End data with <CR><LF>.<CR><LF>')



class SMTPServer(asyncore.dispatcher):
    # SMTPChannel class to use for managing client connections
    channel_class = SMTPChannel

    def __init__(self, localaddr, remoteaddr):
        self._localaddr = localaddr
        self._remoteaddr = remoteaddr
        asyncore.dispatcher.__init__(self)
        try:
            self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
            # try to re-use a server port if possible
            self.set_reuse_addr()
            self.bind(localaddr)
            self.listen(5)
        except:
            self.close()
            raise
        else:
            print('%s started at %s\n\tLocal addr: %s\n\tRemote addr:%s' % (
                self.__class__.__name__, time.ctime(time.time()),
                localaddr, remoteaddr), file=DEBUGSTREAM)

    def handle_accepted(self, conn, addr):
        print('Incoming connection from %s' % repr(addr), file=DEBUGSTREAM)
        channel = self.channel_class(self, conn, addr)

    # API for "doing something useful with the message"
    def process_message(self, peer, mailfrom, rcpttos, data):
        """Override this abstract method to handle messages from the client.

        peer is a tuple containing (ipaddr, port) of the client that made the
        socket connection to our smtp port.

        mailfrom is the raw address the client claims the message is coming
        from.

        rcpttos is a list of raw addresses the client wishes to deliver the
        message to.

        data is a string containing the entire full text of the message,
        headers (if supplied) and all.  It has been `de-transparencied'
        according to RFC 821, Section 4.5.2.  In other words, a line
        containing a `.' followed by other text has had the leading dot
        removed.

        This function should return None, for a normal `250 Ok' response;
        otherwise it returns the desired response string in RFC 821 format.

        """
        raise NotImplementedError



class DebuggingServer(SMTPServer):
    # Do something with the gathered message
    def process_message(self, peer, mailfrom, rcpttos, data):
        inheaders = 1
        lines = data.split('\n')
        print('---------- MESSAGE FOLLOWS ----------')
        for line in lines:
            # headers first
            if inheaders and not line:
                print('X-Peer:', peer[0])
                inheaders = 0
            print(line)
        print('------------ END MESSAGE ------------')



class PureProxy(SMTPServer):
    def process_message(self, peer, mailfrom, rcpttos, data):
        lines = data.split('\n')
        # Look for the last header
        i = 0
        for line in lines:
            if not line:
                break
            i += 1
        lines.insert(i, 'X-Peer: %s' % peer[0])
        data = NEWLINE.join(lines)
        refused = self._deliver(mailfrom, rcpttos, data)
        # TBD: what to do with refused addresses?
        print('we got some refusals:', refused, file=DEBUGSTREAM)

    def _deliver(self, mailfrom, rcpttos, data):
        import smtplib
        refused = {}
        try:
            s = smtplib.SMTP()
            s.connect(self._remoteaddr[0], self._remoteaddr[1])
            try:
                refused = s.sendmail(mailfrom, rcpttos, data)
            finally:
                s.quit()
        except smtplib.SMTPRecipientsRefused as e:
            print('got SMTPRecipientsRefused', file=DEBUGSTREAM)
            refused = e.recipients
        except (socket.error, smtplib.SMTPException) as e:
            print('got', e.__class__, file=DEBUGSTREAM)
            # All recipients were refused.  If the exception had an associated
            # error code, use it.  Otherwise,fake it with a non-triggering
            # exception code.
            errcode = getattr(e, 'smtp_code', -1)
            errmsg = getattr(e, 'smtp_error', 'ignore')
            for r in rcpttos:
                refused[r] = (errcode, errmsg)
        return refused



class MailmanProxy(PureProxy):
    def process_message(self, peer, mailfrom, rcpttos, data):
        from io import StringIO
        from Mailman import Utils
        from Mailman import Message
        from Mailman import MailList
        # If the message is to a Mailman mailing list, then we'll invoke the
        # Mailman script directly, without going through the real smtpd.
        # Otherwise we'll forward it to the local proxy for disposition.
        listnames = []
        for rcpt in rcpttos:
            local = rcpt.lower().split('@')[0]
            # We allow the following variations on the theme
            #   listname
            #   listname-admin
            #   listname-owner
            #   listname-request
            #   listname-join
            #   listname-leave
            parts = local.split('-')
            if len(parts) > 2:
                continue
            listname = parts[0]
            if len(parts) == 2:
                command = parts[1]
            else:
                command = ''
            if not Utils.list_exists(listname) or command not in (
                    '', 'admin', 'owner', 'request', 'join', 'leave'):
                continue
            listnames.append((rcpt, listname, command))
        # Remove all list recipients from rcpttos and forward what we're not
        # going to take care of ourselves.  Linear removal should be fine
        # since we don't expect a large number of recipients.
        for rcpt, listname, command in listnames:
            rcpttos.remove(rcpt)
        # If there's any non-list destined recipients left,
        print('forwarding recips:', ' '.join(rcpttos), file=DEBUGSTREAM)
        if rcpttos:
            refused = self._deliver(mailfrom, rcpttos, data)
            # TBD: what to do with refused addresses?
            print('we got refusals:', refused, file=DEBUGSTREAM)
        # Now deliver directly to the list commands
        mlists = {}
        s = StringIO(data)
        msg = Message.Message(s)
        # These headers are required for the proper execution of Mailman.  All
        # MTAs in existence seem to add these if the original message doesn't
        # have them.
        if not msg.get('from'):
            msg['From'] = mailfrom
        if not msg.get('date'):
            msg['Date'] = time.ctime(time.time())
        for rcpt, listname, command in listnames:
            print('sending message to', rcpt, file=DEBUGSTREAM)
            mlist = mlists.get(listname)
            if not mlist:
                mlist = MailList.MailList(listname, lock=0)
                mlists[listname] = mlist
            # dispatch on the type of command
            if command == '':
                # post
                msg.Enqueue(mlist, tolist=1)
            elif command == 'admin':
                msg.Enqueue(mlist, toadmin=1)
            elif command == 'owner':
                msg.Enqueue(mlist, toowner=1)
            elif command == 'request':
                msg.Enqueue(mlist, torequest=1)
            elif command in ('join', 'leave'):
                # TBD: this is a hack!
                if command == 'join':
                    msg['Subject'] = 'subscribe'
                else:
                    msg['Subject'] = 'unsubscribe'
                msg.Enqueue(mlist, torequest=1)



class Options:
    setuid = 1
    classname = 'PureProxy'



def parseargs():
    global DEBUGSTREAM
    try:
        opts, args = getopt.getopt(
            sys.argv[1:], 'nVhc:d',
            ['class=', 'nosetuid', 'version', 'help', 'debug'])
    except getopt.error as e:
        usage(1, e)

    options = Options()
    for opt, arg in opts:
        if opt in ('-h', '--help'):
            usage(0)
        elif opt in ('-V', '--version'):
            print(__version__, file=sys.stderr)
            sys.exit(0)
        elif opt in ('-n', '--nosetuid'):
            options.setuid = 0
        elif opt in ('-c', '--class'):
            options.classname = arg
        elif opt in ('-d', '--debug'):
            DEBUGSTREAM = sys.stderr

    # parse the rest of the arguments
    if len(args) < 1:
        localspec = 'localhost:8025'
        remotespec = 'localhost:25'
    elif len(args) < 2:
        localspec = args[0]
        remotespec = 'localhost:25'
    elif len(args) < 3:
        localspec = args[0]
        remotespec = args[1]
    else:
        usage(1, 'Invalid arguments: %s' % COMMASPACE.join(args))

    # split into host/port pairs
    i = localspec.find(':')
    if i < 0:
        usage(1, 'Bad local spec: %s' % localspec)
    options.localhost = localspec[:i]
    try:
        options.localport = int(localspec[i+1:])
    except ValueError:
        usage(1, 'Bad local port: %s' % localspec)
    i = remotespec.find(':')
    if i < 0:
        usage(1, 'Bad remote spec: %s' % remotespec)
    options.remotehost = remotespec[:i]
    try:
        options.remoteport = int(remotespec[i+1:])
    except ValueError:
        usage(1, 'Bad remote port: %s' % remotespec)
    return options



if __name__ == '__main__':
    options = parseargs()
    # Become nobody
    classname = options.classname
    if "." in classname:
        lastdot = classname.rfind(".")
        mod = __import__(classname[:lastdot], globals(), locals(), [""])
        classname = classname[lastdot+1:]
    else:
        import __main__ as mod
    class_ = getattr(mod, classname)
    proxy = class_((options.localhost, options.localport),
                   (options.remotehost, options.remoteport))
    if options.setuid:
        try:
            import pwd
        except ImportError:
            print('Cannot import module "pwd"; try running with -n option.', file=sys.stderr)
            sys.exit(1)
        nobody = pwd.getpwnam('nobody')[2]
        try:
            os.setuid(nobody)
        except OSError as e:
            if e.errno != errno.EPERM: raise
            print('Cannot setuid "nobody"; try running with -n option.', file=sys.stderr)
            sys.exit(1)
    try:
        asyncore.loop()
    except KeyboardInterrupt:
        pass
