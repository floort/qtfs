#!/usr/bin/env python

###############################################################################
# Copyright (c) 2010, Floor Terra <floort@gmail.com>
# 
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
# 
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
###############################################################################

from struct import unpack, pack
import sys, os, copy

HAS_CHILDREN = set([
	"moov", "trak", "mdia", "minf","stbl", "dinf",
])


def get_atom_tree(f, startbyte=0, endbyte=False):
	"""Return the full atom tree of the file.
	"""
	tree = []
	if not endbyte:
		f.seek(0, os.SEEK_END)
		endbyte = f.tell()
	f.seek(startbyte)
	current_byte = startbyte
	while f.tell() < endbyte:
		data = f.read(8)
		length, name = unpack(">l4s", data)
		start = f.tell() - 8
		if name in HAS_CHILDREN:
			children = get_atom_tree(f, start + 8, start + length)
		else:
			children = None
		tree.append((start, length, name, children))
		f.seek(start + length, os.SEEK_SET)
	return tree

def print_atom_tree(t, ntabs = 0):
	"""Print the atom tree t.
	"""
	for a in t:
		print ntabs * "\t", "[%s @%Xd len:%d]" % (a[2], a[0], a[1])
		if a[3]:
			print_atom_tree(a[3], ntabs+1)

def get_path(t, p):
	"""Walk the tree and get all atoms matching the given path.
	"""
	items = []
	for a in t:
		if a[2] == p[0]:
			if len(p) == 1:
				items.append(a)
			else:
				items += get_path(a[3], p[1:])
	return items


if __name__ == "__main__":
	# Check arguments
	if len(sys.argv) == 2:
		infile = open(sys.argv[1])
		tree = get_atom_tree(infile)
		print_atom_tree(tree)
		sys.exit(0)
	if len(sys.argv) != 3:
		print "Usage: %s <infile> <outfile>" % (sys.argv[0])
		sys.exit(1)
	# Open and parse the input file
	infile = open(sys.argv[1])
	tree = get_atom_tree(infile)
	# Check if the first atom is an "ftyp" atom
	# and the last atom is the "moov" atom
	if tree[0][2] != "ftyp":
		print "Error: the first atom should be of type 'ftyp' (found '%s')" % (tree[0][2])
		sys.exit(1)
	if tree[-1][2] != "moov":
		print "Error: the last atom should be of type 'moov' (found '%s')" % (tree[-1][2])
		sys.exit(1)
	# Open the output file for writing
	outfile = open(sys.argv[2], "r+b")
	# Copy the input file, but with the 'moov' atom inserted after the
	# 'ftyp' atom.
	infile.seek(tree[0][0], os.SEEK_SET) # Seek to start of 'ftyp'
	outfile.write(infile.read(tree[0][1]))
	infile.seek(tree[-1][0], os.SEEK_SET)
	outfile.write(infile.read(tree[-1][1]))
	# Copy the rest of the atoms
	for a in tree[1:-1]:
		infile.seek(a[0], os.SEEK_SET)
		outfile.write(infile.read(a[1]))
	infile.close()
	# As explained by the web-page 
	# http://atomicparsley.sourceforge.net/mpeg-4files.html 
	# modify moov.trak.mdia.minf.stbl.stco to point to the new 'mdat'
	# atom.
	# New location - old location
	moov_offset = tree[0][1] - tree[-1][0]# new location = len(ftyp_atom)
	mdat_offset = tree[-1][1] # the moov atom is inserted in front of mdat.
	stco = get_path(tree, ["moov", "trak", "mdia", "minf", "stbl", "stco"])
	for atom in stco:
		# Seek to the new location of the stco atom
		# The 12 bytes extra is to skip the length, name, version and
		# flags of the atom.
		outfile.seek(atom[0]+moov_offset + 12, os.SEEK_SET)
		num_pointers = unpack(">l", outfile.read(4))[0]
		# Correct the offset for each pointer
		for i in xrange(num_pointers):
			# Read the pointer
			pointer = unpack(">l", outfile.read(4))[0]
			# Seek back to start of pointer
			outfile.seek(-4, os.SEEK_CUR)
			# Write pointer with offset
			outfile.write(pack(">l", pointer + mdat_offset))
	outfile.close()


