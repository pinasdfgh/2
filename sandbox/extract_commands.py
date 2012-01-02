import re


cmd_re = re.compile(r'{\s*(CANON[^}]*)}')
rc_re = re.compile(r'{\s*(CANON_USB_CONTROL_[^}]*)}')

cmd_c = open('commands.c').read()
cmds = cmd_re.findall(cmd_c)
cmds = [map(str.strip, cmd.split(',')) for cmd in cmds]

print
all = []
for c_idx, description, cmd1, cmd2, cmd3, return_length in cmds:
    desc = c_idx.replace('CANON_USB_FUNCTION_', '')
    all.append(desc)
    print "%s = {" % desc
    print "    'c_idx': '" + c_idx + "',"
    print "    'description': " + description + ","
    print "    'cmd1': " + cmd1 + ","
    print "    'cmd2': " + cmd2 + ","
    print "    'cmd3': " + cmd3 + ","
    print "    'return_length': " + return_length + " }"
    print

print 'ALL = [' + ', '.join(all) + ']'

rc_c = open('control_commands.c').read()
rc_cmds = rc_re.findall(rc_c)
rc_cmds = [map(str.strip, cmd.split(',')) for cmd in rc_cmds]
all = []
for c_idx, description, value, cmd_len, reply_len in rc_cmds:
    if c_idx == '0': continue
    desc = c_idx.replace('CANON_USB_CONTROL_', 'RC_')
    all.append(desc)
    print "%s = {" % desc
    print "    'c_idx': '" + c_idx + "',"
    print "    'description': " + description + ","
    print "    'value': " + value + ","
    print "    'cmd_len': " + cmd_len + ","
    print "    'reply_len': " + reply_len + " }"
    print

print 'ALL_RC = [' + ', '.join(all) + ']'

