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
from xml.etree import ElementTree	# fast xml parser module
import xml.sax
import string, codecs
import time, datetime
import os.path
import sys,getopt	# handle commande-line arguments
import sqlite3

__version__="0.1"
default_file='test.xml'
nbNode=0
nbPlace=0

def et1_parse(fname):
	# parse using ElementTree.parse (DOM)
	# very powerful technique but load all the XML file into memory before parsing
	
	tree=ElementTree.parse(fname)
	root=tree.getroot()
	nodes=root.getiterator("node")
	nbPlace=0
	nbNode=len(nodes)
	for node in nodes:	# scan each nodes
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
	
def et2_parse(fname):
	# parse using ElementTree.iterparse (SAX)
	# do not load the whole file into memory, very fast
	nbNodes=0
	nodes={}
	curr_node = None
	nbWays=0
	ways={}
	curr_way = None
	nbRelations=0
	relations={}
	curr_relation = None
	nbPlace=0
	
	context=ElementTree.iterparse(fname,events=("start","end"))
	context=iter(context)
	event, root = context.next()
	for event, elem in context:
		if event=="start":
			if elem.tag=='node':
				curr_node=Node(id=elem.attrib['id'],lon=elem.attrib['lon'],lat=elem.attrib['lat'])
			elif elem.tag=='way':
				curr_way=Way(id=elem.attrib['id'])
			elif elem.tag=='relation':
				curr_relation=Relation(id=elem.attrib['id'])
			elif elem.tag == 'tag':
				if curr_node:
					curr_node.tags[elem.attrib['k']] = elem.attrib['v']
				elif curr_way:
					curr_way.tags[elem.attrib['k']] = elem.attrib['v']
				elif curr_relation:
					curr_relation.tags[elem.attrib['k']] = elem.attrib['v']
			elif elem.tag == "nd":
				assert curr_node is None, "curr_node (%r) is non-none" % (curr_node)
				assert curr_way is not None, "curr_way is None"
				curr_way.nodes.append(NodePlaceHolder(id=elem.attrib['ref']))
			elif elem.tag == "member":
				assert curr_node is None, "curr_node (%r) is non-none" % (curr_node)
				assert curr_way is None, "curr_way (%r) is non-none" % (curr_way)
				assert curr_relation is not None, "curr_relation is None"
				curr_relation.members.append(NodePlaceHolder(id=elem.attrib['ref'], type=elem.attrib['type']))
			else:
				print "unknown element %s" % elem.tag
		elif event=="end":
			if elem.tag=='node':
				try:
					curr_node.type=curr_node.tags['place']
					if curr_node.type=='town' or curr_node.type=='city' or curr_node.type=='village':
						try:
							curr_node.name=curr_node.tags['name']
						except:
							curr_node.name=""
						try:
							curr_node.pop=int(curr_node.tags['population'])
						except:
							curr_node.pop=-1
						#print curr_node.id,curr_node.name
						nodes[curr_node.id] = curr_node
					curr_node = None
				except:
					curr_node = None
				nbNodes=nbNodes+1
			elif elem.tag=='way':
				curr_way=None
				nbWays=nbWays+1
			elif elem.tag=='relation':
				curr_relation=None
				nbRelations=nbRelations+1
			elem.clear()	# remove leme from memory
			
	root.clear()
	nbPlace=len(nodes)
	
	return (nbNodes,nbPlace)

class Node(object):
    def __init__(self, id=None, lon=None, lat=None, tags=None):
        self.id = id
        self.lon, self.lat = lon, lat
        if tags:
            self.tags = tags
        else:
            self.tags = {}

    def __repr__(self):
        return "Node(id=%r, lon=%r, lat=%r, tags=%r)" % (self.id, self.lon, self.lat, self.tags)

class Way(object):
    def __init__(self, id, nodes=None, tags=None):
        self.id = id
        if nodes:
            self.nodes = nodes
        else:
            self.nodes = []
        if tags:
            self.tags = tags
        else:
            self.tags = {}

    def __repr__(self):
        return "Way(id=%r, nodes=%r, tags=%r)" % (self.id, self.nodes, self.tags)

class Relation(object):
    def __init__(self, id, members=None, tags=None):
      self.id = id
      if members:
          self.members = None
      else:
          self.members = []
      if tags:
          self.tags = tags
      else:
          self.tags = {}
      
    def __repr__(self):
      return "Relation(id=%r, members=%r, tags=%r)" % (self.id, self.members, self.tags)

class NodePlaceHolder(object):
    def __init__(self, id, type=None):
        self.id = id
        self.type = type

    def __repr__(self):
        return "NodePlaceHolder(id=%r, type=%r)" % (self.id, self.type)

class OSMXMLFile(object):
	def __init__(self, filename, loadRelated=False):
		self.filename = filename
		self.loadRelated=loadRelated
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

		# if requested : load related elements *** DO NOT WORKS ***
		if self.loadRelated:
			loadWay=OSMWayLoadingList()
			loadWay.build(self.relations,self.ways,self.nodes)
			parser=xml.sax.make_parser()
			parser.setContentHandler(OSMWayParser(self,loadWay))
			parser.parse(self.filename)
			
			loadNode=OSMNodeLoadingList()
			loadNode.build(self.ways,self.nodes)
			parser=xml.sax.make_parser()
			parser.setContentHandler(OSMNodeParser(self,loadNode))
			parser.parse(self.filename)
			
			for way in self.ways.values():
				try:
					way.nodes = [self.nodes[node_pl.id] for node_pl in way.nodes]
				except:
					print "missing nodes for way",way.id

			for relation in self.relations.values():
				try:
					relation.members = [self.__get_obj(obj_pl.id, obj_pl.type) for obj_pl in relation.members]
				except:
					print "missing membres for relation",relation.id
	
		# convert them back to lists
		self.nodes = self.nodes.values()
		self.ways = self.ways.values()
		self.relations = self.relations.values()

class OSMLoadingList():
	def __init__(self):
		self.nb=0
		self.list=[]

class OSMNodeLoadingList(OSMLoadingList):
	def __init__(self):
		OSMLoadingList.__init__(self)
		self.nbNodes=0
		self.nodes={}
		
	def build(self,ways,nodes):
		for w in ways:
			for n in w.nodes:
				if n.id not in nodes:
					self.list.append(n.id)

class OSMWayLoadingList(OSMLoadingList):
	def __init__(self):
		OSMLoadingList.__init__(self)
		self.nbWays=0
		self.ways={}
		
	def build(self,relations,ways,nodes):
		for r in relations:
			for m in r.members:
				if m.type=='node':
					if m.id not in nodes:
						self.list.append(m.id)			
				elif m.type=='way':
					if m.id not in ways:
						self.list.append(m.id)

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
	
	osm=OSMXMLFile(fname,loadRelated=False)
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
	(nbtot,nb)=et2_parse(file)
	t0=time.time()-t0
	print "> %d nodes parsed, %d match" % (nbtot,nb)
	print "> element tree parsing : %.1f seconds" % t0

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
	