import networkx as nx
import numpy as np
import pandas as pd
import copy
from tqdm import tqdm
import anndata
from swan_vis.utils import *

# super class that both SwanGraph and PlottedGraph inherit from.
# all functions that both subclasses will use are in here.
class Graph:
	def __init__(self):
		"""
		A general graph class to represent a transcriptome.

		Attributes
		----------
		datasets (list of str):
			Names of datasets in the Graph
		counts (list of str):
			Names of columns holding counts in the Graph
		tpm (list of str):
			Names of columns holding tpm values in the Graph
		loc_df (pandas DataFrame):
			DataFrame of all unique observed genomic
			coordinates in the transcriptome
		edge_df (pandas DataFrame):
			DataFrame of all unique observed exonic or intronic
			combinations of splice sites in the transcriptome
		t_df (pandas DataFrame):
			DataFrame of all unique transcripts found
			in the transcriptome
		"""

		self.datasets = []
		self.annotation = False
		self.loc_df = pd.DataFrame(columns=['chrom', 'coord',
									   'vertex_id'])
		self.edge_df = pd.DataFrame(columns=['v1', 'v2', 'strand',
											 'edge_type', 'edge_id'])
		self.adata = anndata.AnnData()
		self.t_df = pd.DataFrame(columns=['tname',
			'gid', 'gname', 'path', 'tid'])

	##########################################################################
	################# Related to checking contents of Graph ##################
	##########################################################################

	# check that input datasets are in the Graph:
	def check_datasets(self, datasets):

		# make sure we have an iterable
		if type(datasets) != list:
			datasets = [datasets]

		g_datasets = self.get_dataset_cols()
		for d in datasets:
			if d not in g_datasets:
				raise Exception('Dataset {} not present in graph. '
								'Datasets in graph are {}'.format(d, g_datasets))


	# check that input datasets have abundance data in the Graph:
	def check_abundances(self, datasets):

		# make sure we have an iterable
		if type(datasets) != list:
			datasets = [datasets]

		ab_cols = self.get_count_cols()
		for d in datasets:
			if '{}_counts'.format(d) not in ab_cols:
				raise Exception('Abundance for dataset {} not present in graph. '
								'Datasets with abundance information '
								'in graph are {}'.format(d, ab_cols))

	# check that de tests have been run
	def check_de(self, de_type):
		if de_type == 'transcript':
			if not self.det_test.empty:
				return True
		elif de_type == 'gene':
			if not self.deg_test.emtpy:
				return False
		else:
			return False

	# check if there are even any datasets
	def check_if_any_datasets(self, task):
		if self.datasets == None:
			raise Exception('No datasets found in graph. '
				'Cannot perform {}'.format(task))

	# check if gid is in SwanGraph
	def check_gene(self, gid):
		if gid not in self.t_df.gid.tolist():
			raise Exception('Gene {} not found in Graph.'.format(gid))

	# check if tid is in SwanGraph
	def check_transcript(self, tid):
		if tid not in self.t_df.tid.tolist():
			raise Exception('Transcript {} not found in Graph.'.format(tid))


	##########################################################################
	####################### Related to creating Graph ########################
	##########################################################################

	# update ids according to coordinates in loc_df, edge_df, and t_df
	def update_ids(self, id_map=None, verbose=False):
		"""
		Reindex SwanGraph using sorted genomic coordinates (chromosome, coord).
		Modifies vertex_ids and replaces them in edge_df and t_df.loc_path.

		Parameters:
			id_map (dict): Dictionary mapping {old_vertex_id: new_vertex_id}
				Default: None, will order based on genomic location
			verbose (bool): Display progress
		"""

		# if the user didn't already input an id map, just order
		# according to genomic position
		if not id_map:
			id_map = self.get_ordered_id_map()

		# convert dfs into dicts for the next steps
		self.dfs_to_dicts()

		# update the ids according to id_map
		self.update_loc_df_ids(id_map, verbose)
		self.update_edge_df_ids(id_map, verbose)

		# convert back to dfs
		self.dicts_to_dfs()

		# and add new location paths from the updated vertex ids
		self.get_loc_path()

	# get a dictionary mapping vertex id to ordered new vertex id
	def get_ordered_id_map(self):

		# sort each of the dfs by chrom, coord either ascending
		# or descending based on strand
		self.loc_df.sort_values(['chrom', 'coord'],
								 ascending=[True, True],
								 inplace=True)

		# dictionary mapping vertex_id to new_id
		self.loc_df['new_id'] = [i for i in range(len(self.loc_df.index))]
		id_map = self.loc_df['new_id'].to_dict()
		self.loc_df.drop('new_id', axis=1, inplace=True)

		return id_map

	def update_loc_df_ids(self, id_map, verbose):
		"""
		Update the vertex IDs in self.loc_df dictionary according to id_map.

		Parameters:
			id_map (dict): Map of {old_vertex_id: new_vertex_id}
			verbose (bool): Display progress
		"""

		loc_df = {}

		if verbose:
			pbar = tqdm(total=len(id_map.items()))
			counter = 0

		for old_id, new_id in id_map.items():
			if verbose:
				counter+=1
				if counter % 1000 == 0:
					pbar.update(1000)
					pbar.set_description('Reindexing vertices')

			loc_df[new_id] = self.loc_df[old_id]
			loc_df[new_id]['vertex_id'] = new_id

		if verbose:
			pbar.close()

		self.loc_df = loc_df

	def update_edge_df_ids(self, id_map, verbose):
		"""
		Update the vertex IDs in self.edge_df (v1 and v2) dictionary according
		to id_map.

		Parameters:
			id_map (dict): Map of {old_vertex_id: new_vertex_id}
			verbose (bool): Display progress
		"""

		edge_df = {}

		if verbose:
			pbar = tqdm(total=len(id_map.items()))
			counter = 0

		for edge_id, item in self.edge_df.items():

			if verbose:
				counter+=1
				if counter % 1000 == 0:
					pbar.update(1000)
					pbar.set_description('Reindexing edges')

			edge_df[edge_id] = {}
			edge_df[edge_id]['v1'] = id_map[item['v1']]
			edge_df[edge_id]['v2'] = id_map[item['v2']]

			# edge id stays the same, just change the vertices associated
			# with it
			edge_df[edge_id]['edge_id'] = edge_id

		if verbose:
			pbar.close()

		self.edge_df = edge_df

	def get_loc_path(self):
		"""
		Determine the location path of each transcript in the SwanGraph using
		the edge path and add it to the SwanGraph.
		"""
		def get_transcript_loc_path(path, edge_df):
			start_v1 = [edge_df.loc[path[0], 'v1']]
			v2s = edge_df.loc[path, 'v2'].tolist()
			loc_path = start_v1+v2s
			return loc_path

		self.t_df['loc_path'] = self.t_df.apply(lambda x: \
			get_transcript_loc_path(x.path, self.edge_df), axis=1)

	def create_graph_from_dfs(self):
		"""
		Create the networkx graph object from t_df. 
		"""

		G = nx.DiGraph()

		# add nodes to graph from transcript paths
		paths = self.t_df.loc_path.tolist()
		for path in paths:
			nx.add_path(G, path)

		self.G = G

	# order edge df based on source id
	def order_edge_df(self):
		self.edge_df.sort_values(by=['v1', 'v2'], inplace=True)


	##########################################################################
	####### Functions to switch back and forth between dfs and dicts #########
	##########################################################################

	# convert loc_df, edge_df, and t_df to dictionaries
	def dfs_to_dicts(self):

		self.loc_df = self.loc_df.to_dict('index')
		self.edge_df = self.edge_df.to_dict('index')
		self.t_df = self.t_df.to_dict('index')

	# convert dictionary versions of loc_df, edge_df, and t_df to dfs
	def dicts_to_dfs(self):

		# loc_df
		self.loc_df = pd.DataFrame.from_dict(self.loc_df, orient='index')
		self.loc_df.index.names = ['vertex_id']

		# edge_df
		self.edge_df = pd.DataFrame.from_dict(self.edge_df, orient='index')
		self.loc_df.index.names = ['edge_id']

		# t_df
		self.t_df = pd.DataFrame.from_dict(self.t_df, orient='index')
		self.t_df.index.names = ['tid']

	##########################################################################
	############################# Other utilities ############################
	##########################################################################

	# check if anything has been added to the graph yet
	def is_empty(self):
		if len(self.adata.obs.index) == 0:
			return True
		else:
			return False

	# check if novelty information is in the graph
	def has_novelty(self):
		if 'novelty' in self.t_df.columns.tolist():
			return True
		else: return False

	##########################################################################
	############################# Accessing data ############################
	##########################################################################

	# gets the names of the dataset columns in the graph
	def get_dataset_cols(self, include_annotation=True):
		if include_annotation:
			return self.datasets
		elif not include_annotation:
			if 'annotation' not in self.datasets:
				return self.datasets
			else:
				datasets = copy.deepcopy(self.datasets)
				datasets.remove('annotation')
				return datasets

	# gets the names of the counts columns in the graph
	# returns None if no counts have been added
	# if datasets option given, returns the counts
	# columns associated with the input datasets
	def get_count_cols(self, datasets=None):

		if datasets:
			if type(datasets) != list:
				datasets = [datasets]
			self.check_abundances(datasets)
			counts_cols = []
			for d in datasets:
				counts_cols.append('{}_counts'.format(d))
			return counts_cols

		return self.counts

	# gets the names of tpm columns in the graph
	# returns None if no counts have been added
	# if datasets option given, returns the counts
	# columns associated with the input datasets
	def get_tpm_cols(self, datasets=None):

		if datasets:
			if type(datasets) != list:
				datasets = [datasets]
			self.check_abundances(datasets)
			tpm_cols = []
			for d in datasets:
				tpm_cols.append('{}_tpm'.format(d))
			return tpm_cols

		return self.tpm

	# gets strandedness of transcript from transcript id
	def get_strand_from_tid(self, tid):
		return self.loc_df.loc[self.t_df.loc[tid, 'path'][0], 'strand']

	# gets strandedness of transcript from gene id
	def get_strand_from_gid(self, gid):
		vertex = self.t_df.loc[self.t_df.gid == gid].path.tolist()[0][0]
		return self.loc_df.loc[vertex, 'strand']

	# get the path from the transcript id
	def get_path_from_tid(self, tid):
		return self.t_df.loc[tid].path

	# get the gene id from the gene name
	def get_gid_from_gname(self, gname):
		try:
			gid = self.t_df.loc[self.t_df.gname == gname, 'gid'].tolist()[0]
		except:
			gid = gname
		return gid

	# get the gene id from the transcript id
	def get_gid_from_tid(self, tid):
		return self.t_df.loc[tid, 'gid']

	# returns the min and max coordinates of an input gene
	def get_gene_min_max(self, gid):

		# get all starts and stops from gene and their coordinates
		paths = self.t_df.loc[self.t_df.gid == gid].path.tolist()
		starts = np.unique([path[0] for path in paths]).tolist()
		stops = np.unique([path[-1] for path in paths]).tolist()
		coords = self.loc_df.loc[starts+stops, 'coord']

		return int(min(coords)), int(max(coords))

	# returns the min and max coordinates of an input transcript
	def get_transcript_min_max(self, tid):

		path = self.t_df.loc[tid, 'path']
		ends = [path[0], path[-1]]
		end_coords = self.loc_df.loc[ends, 'coord']

		return int(min(end_coords)), int(max(end_coords))

###########################################################################
################################## Extras #################################
##########################################################################

	 # subset a graph based on a gene
	def subset_on_gene(self, gid):

		# make sure this gid is even in the Graph
		self.check_gene(gid)

		# subset t_df first, it's the easiest
		t_df = self.t_df.loc[self.t_df.gid == gid].copy(deep=True)
		t_df['path'] = self.t_df.loc[self.t_df.gid == gid].apply(
				lambda x: copy.deepcopy(x.path), axis=1)

		# subset loc_df based on all the locs that are in the paths from
		# the already-subset t_df
		paths = t_df['path'].tolist()
		locs = [node for path in paths for node in path]
		locs = np.unique(locs)
		loc_df = self.loc_df.loc[locs].copy(deep=True)

		# subset edge_df based on all the edges that are in the paths from
		# the alread-subset t_df
		edges = [(v1,v2) for path in paths for v1,v2 in zip(path[:-1],path[1:])]
		edges = list(set(edges))
		edge_df = self.edge_df.loc[edges].copy(deep=True)

		# create a new graph that's been subset
		subset_sg = Graph()
		subset_self.loc_df = loc_df
		subset_self.edge_df = edge_df
		subset_self.t_df = t_df
		subset_self.datasets = self.datasets
		subset_self.counts = self.counts
		subset_self.tpm = self.tpm

		# renumber locs
		subset_self.update_ids()

		# finally create the graph
		subset_self.create_graph_from_dfs()

		return subset_sg

# # convert a list of vertex ids to a list of edge ids
# def vertex_to_edge_path(path):
# 	return [(v1,v2) for v1,v2 in zip(path[:-1],path[1:])]
