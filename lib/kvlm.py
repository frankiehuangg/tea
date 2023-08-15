import collections

def kvlm_parse(raw, start=0, dct=None):
    """
    Key-Value List with Message
    """
    FIRST_ITERATION = not dct
    if (FIRST_ITERATION):
        dct = collections.OrderedDict()

    # Search for the next space and the next newline
    space = raw.find(b' ', start)
    newline = raw.find(b'\n', start)

    # If space appears before newline, we have a keyword

    # Best case
    # =========
    # If newline appears first (or there's no space at all, in which
    # case find returns -1), we assume a blank line. A blank line means
    # the remainder of the data is the message
    READING_MESSAGE = (space < 0) or (newline < space)
    if (READING_MESSAGE):
        assert newline == start
        dct[None] = raw[start+1:]
        return dct

    # Recursive case
    # ==============
    # We read a key-value pair and recurse for the next
    key = raw[start:space]

    # Find the end of the value. Continuation lines begin with a
    # space, so we loop until we find a '\n' not followed by a space.
    end = start
    while (True):
        end = raw.find(b'\n', end+1)
        if (raw[end+1] != ord(' ')):
            break

    # Grab the value
    # Also, drop the leading space on continuation lines
    value = raw[space+1:end].replace(b'\n ', b'\n')

    # Don't overwrite existing data contents
    if (key in dct):
        if (type(dct[key]) == list):
            dct[key].append(value)
        else:
            dct[key] = [ dct[key], value ]
    else:
        dct[key] = value

    return kvlm_parse(raw, start=end+1, dct=dct)

def kvlm_serialize(kvlm):
    ret = b''

    # Output fields
    for k in kvlm.keys():
        # Skip the message itself
        if (k == None):
            continue

        val = kvlm[k]

        # Normalize to a list
        if (type(val) != list):
            val = [ val ]

        for v in val:
            ret += k + b' ' + (v.replace(b'\n', b'\n ')) + b'\n'

    # Append message
    ret += b'\n' + kvlm[None] + b'\n'

    return ret
