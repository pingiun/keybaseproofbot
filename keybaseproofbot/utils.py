import re

def fix_dashes(text):
	""" This function assumes that 'text' has been check to contain 
	'BEGIN PGP MESSAGE' on the first line and 'END PGP MESSAGE' on the last line
	"""

	lines = text.split('\n')
	first = re.compile(r'^.*BEGIN PGP MESSAGE.*$')
	last = re.compile(r'^.*END PGP MESSAGE.*$')
	lines[0] = first.sub('-----BEGIN PGP MESSAGE-----', lines[0])
	lines[-1] = last.sub('-----END PGP MESSAGE-----', lines[-1])
	return '\n'.join(lines)