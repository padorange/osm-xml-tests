#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
	xml_test.py
	-----------
	Test python's xml performances
	
	Implement parser for OSM/XML data
	Function loadRelated is not WORKING
	This function should reparse the tree (for sax) to load nodes related to way that match request
	
	Pierre-Alain Dorange, april 2011
"""

# standard python modules
from xml.etree import cElementTree as ElementTree	# fast xml parser module
import xml.sax
import string, codecs
import time, datetime
import os.path
import sys,getopt	# handle commande-line arguments
import sqlite3

import pyOSM	# pyOSM lib

__version__="0.2"
default_file='test.xml'

def et1_parse(fname):
	# parse using ElementTree.parse (DOM)
	# very powerful technique but load all the XML file into memory before parsing
	
	tree=ElementTree.parse(fname)
	root=tree.getroot()
	nodes=root.getiterator("node")
	nbPlace=0
	nbNode=0
	for node in nodes:	# scan each nodes
		nbNode=nbNode+1
		name=""
		pop=-1
		type=""
		tags=node.getiterator("tag")
		for tag in tags:	# for one node, scan each tags
			k=tag.get("k")
			if k=='place':
				try:
					type=string.lower(tag.get("v"))
					if type=='town' or type=='city' or type=='village':
						nbPlace=nbPlace+1
				except:
					print "* error node #%d : retrieving 'place'" % id
			elif k=='name':
				name=tag.get("v")
			elif k=='population':
				try:
					pop=int(tag.get("v"))
				except:
					pop=-1

	return (nbNode,nbPlace)

class place_parser(pyOSM.osm_parser):
	def __init__(self,filename="test.xml"):
		pyOSM.osm_parser.__init__(self,filename)
	
	def check_elem(self,element):
		try:
			element.type=element.tags['place']
			if element.type=='town' or element.type=='city' or element.type=='village':
				try:
					element.name=element.tags['name']
				except:
					element.name=""
				try:
					element.pop=int(element.tags['population'])
				except:
					element.pop=0
				return element.id
		except:
			element.type=''
			return -1
		
class OSMXMLFile(object):
	def __init__(self, filename):
		self.filename = filename
		self.nodes={}
		self.ways={}
		self.relations={}
		self.nbNodes=0
		self.nbWays=0
		self.nbRelations=0
		
		self.__parse()

	def __get_obj(self, id, type):
		if type == "way":
			return self.ways[id]
		elif type == "node":
			return self.nodes[id]
		else:
			print "Don't know type %r in __get_obj" % (type)
			return None
    
	def __parse(self):
		"""Parse the given XML file"""
		parser=xml.sax.make_parser()
		parser.setContentHandler(OSMXMLFileParser(self))
		parser.parse(self.filename)
	
		# convert them back to lists
		self.nodes = self.nodes.values()
		self.ways = self.ways.values()
		self.relations = self.relations.values()

class OSMWayParser(xml.sax.ContentHandler):
	def __init__(self, containing_obj, loadingList):
		self.containing_obj=containing_obj
		self.loadingList=loadingList
		self.loadingList.nbWays=0
		self.curr_way = None

	def startElement(self, name, attrs):
		if name ==  'way':
			self.loadingList.nbWays=self.loadingList.nbWays+1
			self.curr_way = Way(id=attrs['id'])
                
		elif name == "nd":
			assert self.curr_node is None, "curr_node (%r) is non-none" % (self.curr_node)
			assert self.curr_way is not None, "curr_way is None"
			self.curr_way.nodes.append(NodePlaceHolder(id=attrs['ref']))

	def endElement(self, name):
		if name == "way":
			try:
				if self.curr_way.id in self.loadingList.list:
					self.containing_obj.ways[self.curr_way.id] = self.curr_way
				self.curr_way = None
			except:
				self.curr_way = None

class OSMXMLFileParser(xml.sax.ContentHandler):
	def __init__(self, containing_obj):
		self.containing_obj=containing_obj
		self.containing_obj.nbNodes=0
		self.containing_obj.nbWays=0
		self.containing_obj.nbRelations=0
		self.curr_node = None
		self.curr_way = None
		self.curr_relation = None

	def startElement(self, name, attrs):
		if name == 'node':
			self.containing_obj.nbNodes=self.containing_obj.nbNodes+1
			self.curr_node = Node(id=attrs['id'], lon=attrs['lon'], lat=attrs['lat'])

		elif name == 'way':
			self.containing_obj.nbWays=self.containing_obj.nbWays+1
			self.curr_way = Way(id=attrs['id'])
            
		elif name == 'tag':
			if self.curr_node:
				self.curr_node.tags[attrs['k']] = attrs['v']
			elif self.curr_way:
				self.curr_way.tags[attrs['k']] = attrs['v']
			elif self.curr_relation:
				self.curr_relation.tags[attrs['k']] = attrs['v']
                
		elif name == "nd":
			assert self.curr_node is None, "curr_node (%r) is non-none" % (self.curr_node)
			assert self.curr_way is not None, "curr_way is None"
			self.curr_way.nodes.append(NodePlaceHolder(id=attrs['ref']))
            
		elif name == "relation":
			self.containing_obj.nbRelations=self.containing_obj.nbRelations+1
			assert self.curr_node is None, "curr_node (%r) is non-none" % (self.curr_node)
			assert self.curr_way is None, "curr_way (%r) is non-none" % (self.curr_way)
			assert self.curr_relation is None, "curr_relation (%r) is non-none" % (self.curr_relation)
			self.curr_relation = Relation(id=attrs['id'])
          
		elif name == "member":
			assert self.curr_node is None, "curr_node (%r) is non-none" % (self.curr_node)
			assert self.curr_way is None, "curr_way (%r) is non-none" % (self.curr_way)
			assert self.curr_relation is not None, "curr_relation is None"
			self.curr_relation.members.append(NodePlaceHolder(id=attrs['ref'], type=attrs['type']))
          
		else:
			print "Don't know element %s" % name


	def endElement(self, name):
		#print "End of node " + name
		#assert not self.curr_node and not self.curr_way, "curr_node (%r) and curr_way (%r) are both non-None" % (self.curr_node, self.curr_way)
		if name == "node":
			try:
				self.curr_node.type=self.curr_node.tags['place']
				if self.curr_node.type=='town' or self.curr_node.type=='city' or self.curr_node.type=='village':
					try:
						self.curr_node.name=self.curr_node.tags['name']
					except:
						self.curr_node.name=""
					try:
						self.curr_node.pop=int(self.curr_node.tags['population'])
					except:
						self.curr_node.pop=-1
					self.containing_obj.nodes[self.curr_node.id] = self.curr_node
				self.curr_node = None
			except:
				self.curr_node = None
				            
		elif name == "way":
			try:
				self.curr_way.type=self.curr_way.tags['place']
				if self.curr_way.type=='town' or self.curr_way.type=='city' or self.curr_way.type=='village':
					try:
						self.curr_way.name=self.curr_way.tags['name']
					except:
						self.curr_way.name=""
					try:
						self.curr_way.pop=int(self.curr_way.tags['population'])
					except:
						self.curr_way.pop=-1
					self.containing_obj.ways[self.curr_way.id] = self.curr_way
				self.curr_way = None
			except:
				self.curr_way = None
        
		elif name == "relation":
			try:
				self.curr_relation.type=self.curr_relation.tags['place']
				if self.curr_relation.type=='town' or self.curr_relation.type=='city' or self.curr_relation.type=='village':
					try:
						self.curr_relation.name=self.curr_relation.tags['name']
					except:
						self.curr_relation.name=""
					try:
						self.curr_relation.pop=int(self.curr_relation.tags['population'])
					except:
						self.curr_relation.pop=-1
					self.containing_obj.relations[self.curr_relation.id] = self.curr_relation
				self.curr_relation = None
			except:
				self.curr_relation = None
				 
def sax_parse(fname):
	# parse using ElementTree.iterparse (SAX)
	# do not load the whole file into memory, very fast
	
	osm=OSMXMLFile(fname)
	nbNode=osm.nbNodes
	nbPlace=len(osm.nodes)
	
	return (nbNode,nbPlace)
	
def usage():
	print
	print "xml_test.py usage"
	print "\t-h (--help) : aide (syntaxe)"
	print "\t-f (--file) : fichier à analyser (osm-xml standard format)"

def main(argv):
	try:
		opts,args=getopt.getopt(argv,"hf:",["help","file="])
	except:
		print "syntaxe incorrecte",sys.exc_info(),"\n"
		usage()
		sys.exit(2)
	
	file=default_file
	for opt,arg in opts:
		if opt in ("-h","--help"):
			usage()
			sys.exit()
		elif opt in ("-f","--file"):
			file=arg
	
	try:
		fsize=os.path.getsize(file)
	except:
		print "file trouble",file,"\n",sys.exc_info(),"\n"
		usage()
		sys.exit(2)
	
	if False:
		print "-------------------------------------------------"
		print "ElementTree (DOM)"
		if fsize<100000000:
			t0=time.time()
			(nbtot,nb)=et1_parse(file)
			t0=time.time()-t0
			print "> %d nodes parsed, %d match" % (nbtot,nb)
			print "> element tree parsing : %.1f seconds" % t0
		else:
			print "> do not handle file size > 100 MB",fsize

	print "-------------------------------------------------"
	print "ElementTree (iterparse)"
	t0=time.time()
	p=place_parser(file)
	p.parse()
	t0=time.time()-t0
	print "> element tree parsing : %.1f seconds" % t0
	print "> %d nodes parsed, %d match" % (p.nbNodes,len(p.nodes))
	print "> %d ways parsed, %d match" % (p.nbWays,len(p.ways))
	print "> %d relations parsed, %d match" % (p.nbRelations,len(p.relations))
	t0=time.time()
	p.load_related()
	t0=time.time()-t0
	print "> load related items : %.1f seconds" % t0
	print "> %d nodes parsed, %d total" % (p.nbNodes,len(p.nodes))
	print "> %d ways parsed, %d total" % (p.nbWays,len(p.ways))
	print "> %d relations parsed, %d total" % (p.nbRelations,len(p.relations))
	t0=time.time()
	pois=p.create_nodes("result.osm")
	t0=time.time()-t0
	print "> create pois : %.1f seconds" % t0
	print "> %d pois created" % len(pois)

	if False:
		print "-------------------------------------------------"
		print "xml.sax"
		t0=time.time()
		(nbtot,nb)=sax_parse(file)
		t0=time.time()-t0
		print "> %d nodes parsed, %d match" % (nbtot,nb)
		print "> element tree parsing : %.1f seconds" % t0

	print "-------------------------------------------------"

if __name__ == '__main__' :
    main(sys.argv[1:])
	