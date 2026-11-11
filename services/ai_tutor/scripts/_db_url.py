# Prints SUPABASE_URI from .env with the password URL-encoded.
import re, urllib.parse

line = next(l for l in open('.env') if l.startswith('SUPABASE_URI='))
uri = line.split('=', 1)[1].strip().strip('"\'')
m = re.match(r'(postgresql://)([^:]+):(.*)@([^@]+)$', uri)
print(m[1] + m[2] + ':' + urllib.parse.quote(m[3], safe='') + '@' + m[4])
