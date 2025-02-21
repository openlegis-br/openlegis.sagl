import random
import string

def get_random_string(length):
    result_str = ''.join(random.choice(string.ascii_letters) for i in range(length))
    return(result_str)

return get_random_string(8)
