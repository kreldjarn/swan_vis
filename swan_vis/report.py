from swan_vis.utils import *
from fpdf import FPDF
import matplotlib.pyplot as pyplot

# report for genes - extension of FPDF class
class Report(FPDF):

	def __init__(self,
				 prefix,
				 report_type, 
				 report_cols, 
				 header_cols, 
				 novelty=False,
				 heatmap=False):
		super().__init__(orientation='L')

		# change margins
		self.set_margins(0.5, 0.5, 0.5)

		# set report type, 'browser' or 'swan'
		if report_type != 'browser' and report_type != 'swan':
			raise Exception("Report type must be 'browser' or 'swan'.")
		else: 
			self.report_type = report_type

		# booleans of what's in the report
		self.heatmap = heatmap
		self.novelty = novelty 

		# the columns that we'll include
		self.report_cols = report_cols
		self.header_cols = header_cols
		self.n_dataset_cols = len(self.report_cols)
		
		# prefix for files that we'll pull from 
		self.prefix = prefix

		# color map in case we're making a heatmap
		self.cmap = plt.get_cmap('Spectral_r')

		# settings

		self.entry_height = 20

		# add extra room for the scale/colorbar if we're doing 
		# the browser/heatmap version
		if self.report_type == 'swan':
			self.header_height = 10
		if self.report_type == 'browser':
			self.header_height = 20

		# dataset width is contingent on # of datasets
		# as well as if we're including the novelty column
		if self.novelty:
			self.w_dataset = (146-25)/self.n_dataset_cols
		else:
			self.w_dataset = 146/self.n_dataset_cols

	# header - should differ based on whether it's a browser report or
	# a swan report
	def header(self):
		self.set_font('Arial', 'B', 10)
		
		# transcript ID header
		self.cell(50, self.header_height, 'Transcript ID', border=True, align='C')

		# novelty header (if needed)
		if self.novelty:
			self.cell(25, self.header_height, 'Novelty', border=True, align='C')

		# dataset ID headers
		for col in self.header_cols:
			self.cell(self.w_dataset, self.header_height, col,
					  border=True, align='C')

		# in case we need to add the browser models
		browser_scale_x = self.get_x()
		browser_scale_y = self.get_y()

		# transcript model header
		self.cell(100, self.header_height, 'Transcript Model', border=True, align='C')

		# add scale if we're doing browser models
		if self.report_type == 'browser':
			self.image(self.prefix+'_browser_scale.png',
					   x=browser_scale_x, 
					   y=browser_scale_y+12,
					   w=100, h=50/7)
		self.ln()

	# footer - just add the colorbar if we're using the
	# heatmap option
	def footer(self):
		if self.heatmap:
			self.set_x(77.5)
			self.image(self.prefix+'_colorbar_scale.png',
				w=90, h=135/14)

	# add a transcript model to the report
	def add_transcript(self, entry, oname):

		# entries should not be bolded
		self.set_font('Arial', '', 10)

		# tid
		self.cell(50, self.entry_height, entry['tid'], border=True, align='C')

		# novelty, if necessary
		if self.novelty: 
			self.cell(25, self.entry_height, entry['novelty'],
				border=True, align='C')

		# dataset columns
		for col in self.report_cols:

			# heat map coloring
			if self.heatmap:
				color = self.cmap(entry[col])
				r = color[0]*255
				b = color[1]*255
				g = color[2]*255
				self.set_fill_color(r,b,g)
				border = False
				fill = True
				text = ''
			# TPM	
			elif '_tpm' in col:
				text = str(round(entry[col],2))
				border = True
				fill = False
			# presence/absence
			else:
				text = entry[col]
				if text == True:
					text = 'Yes'
				elif text == False:
					text = 'No'
				border = True
				fill = False 
			self.cell(self.w_dataset, self.entry_height, text,
				border=border, align='C', fill=fill)	
		x = self.get_x()
		y = self.get_y()

		# reset color to white
		self.set_fill_color(255,255,255)

		# embed transcript model
		self.cell(100, self.entry_height, '', border=True)
		self.image(oname, x=x, y=y, w=100, h=20)
		self.ln()

	# writes the pdf to file with the correct formatting
	def write_pdf(self, file):
		with open(file, 'wb') as outfile:
			outfile.write(self.output(dest='S').encode('latin-1'))
