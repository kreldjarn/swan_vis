import networkx as nx
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import pickle
import os
from collections import defaultdict
import SpliceGraph as sg
import PlottedGraph as pg
from utils import *
from plotting_tools import * 

def get_args():

	desc = 'Loads a GTF into a graph'
	parser = argparse.ArgumentParser(description=desc)

	parser.add_argument('-g', dest='graph_file',
		help='Pickled graph file (.p)')
	parser.add_argument('--o', dest='oname', default=None,
		help='Output directory/prefix to store figure')
	parser.add_argument('--agg_nodes', dest='agg_nodes', 
		default=False, action='store_true')

	args = parser.parse_args()

	return args

def make_oname(args, tid):

	oname = args.oname

	if not oname:
		oname = '{}/'.format(os.getcwd())
	else: 
		oname = '{}'.format(oname)


	if args.agg_nodes: oname += '_combined'

	oname += '_{}'.format(tid)
	
	oname += '.png'
	return oname

def main():

	args = get_args()

	# load in pickled data
	with open(args.graph_file, 'rb') as pfile:
		splice_graph = pickle.load(pfile)

	temp = defaultdict()
	temp['color_edges'] = False
	temp['color_nodes'] = False
	temp['color_alt_nodes'] = False
	temp['combine'] = args.agg_nodes
	temp['ann'] = False

	# plot gene graph first
	plotted_graph = pg.PlottedGraph(splice_graph, temp)

	# loop through each transcript path in the graph 
	for tid in plotted_graph.t_df.tid.tolist():
		oname = make_oname(args, tid)
		path = plotted_graph.t_df.loc[tid, 'path']
		plot_overlaid_path(plotted_graph, path, temp, oname)

if __name__ == '__main__': main()