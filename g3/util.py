
def extract_string(data, start):
    end = data[start:].index(0x00)
    return data[start:start+end].tostring()
