key_mapping = {'R': 'signal', 'V': 'voltage', 'I': 'current', 'T': 'temperature',
               't': 'duration', 'E': 'kwh', 'S': 'status'}

status_mapping = {'S': 'start', 'C': 'charging', 'E': 'finished',
                  'U': 'unplugged', 'W': 'waiting', 'R': 'error'}

data_template = {'serial': None, 'voltage': 220, 'current': 10, 'temperature': 40,
                 'duration': 0, 'kwh': 0, 'status': 'idle', 'time': None}

command_mapping = {'serial': '', 'charge_0': 'BG0', 'charge_1': f'BG60',
                   'charge_2': f'BG120', 'charge_3': f'BG180',
                   'set_0': 'AA', 'set_1': 'BB'}
