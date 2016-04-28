# Import -----------------------------------------------------------------------

import os
import pandas as pd
import numpy as np
import pylab
from biokit.stats import mixture
from sequana import running_median

# Class ------------------------------------------------------------------------

class genomecov(object):
    """ Create pandas dataframe of bed file provided by bedtools genomecov (-d).
    
:param input_filename: the input data with results of a bedtools genomecov run.

:Example:

    > mydata = bedtools.genomecov('exemple.bed')
    > mydata.running_median(n=1001, label='rm')
    > mydata.coverage_scaling(method='rm')
    > mydata.compute_zscore(label='zscore)

    """
    def __init__(self, input_filename=None, dataframe=None):
        try:
            self.df = pd.read_table(input_filename, header=None)
            self.df = self.df.rename(columns={0: "chr", 1: "pos", 2: "cov"})
        except IOError as e:
            print("I/0 error({0}): {1}".format(e.errno, e.strerror))

    def __str__(self):
        return self.df.__str__()

    def __len__(self):
        return self.df.__len__()

    def moving_average(self, n, label="ma"):
        """ Do moving average of reads coverage and create a column called 'ma'
        in data frame with results.

        :param n: window's size.

        """
        ret = np.cumsum(np.array(self.df["cov"]), dtype=float)
        ret[n:] = ret[n:] - ret[:-n]
        ma = ret[n - 1:] / n
        mid = int(n / 2)
        self.df["ma"] = pd.Series(ma, index=np.arange(start=mid,
            stop=(len(ma) + mid)))

    def running_median(self, n, label="rm", circular=False):
        """ Do running median of reads coverage and create a column called 'rm'
        in data frame withe results.

        :param n: window's size.

        """
        mid = int(n / 2)
        if(circular):
            cov = list(self.df["cov"])
            cov = cov[-mid:] + cov + cov[:mid]
            rm = list(running_median.RunningMedian(n, cov))
            self.df[label] = pd.Series(rm)
        else:
            rm = list(running_median.RunningMedian(n, self.df["cov"]))
            self.df[label] = pd.Series(rm, index=np.arange(start=mid,
                stop=(len(rm) + mid)))

    def coverage_scaling(self, method="rm", label="scale"):
        """ Normalize data with moving average of coverage and create a column 
        called 'scale' in data frame with results.
        Needs result of moving_average().

        """
        try:
            self.df[label] =  self.df["cov"] / self.df[method] 
        except KeyError:
            print("Column " + method + " is missing.\n",
                    self.__doc__)
            return
        self.df = self.df.replace(np.inf , np.nan)

    def _get_best_gaussian(self, results):
        diff = 100
        for i, value in enumerate(results.mus):
            if(abs(value - 1) < diff):
                diff = value
                indice = i
        return indice

    def compute_zscore(self, k=2, label="zscore", step=10):
        """ Compute zscore of coverage. 
        Needs result of coverage_scaling().

        :param k: Number gaussian predicted in mixture (default = 2)
        :param method: Column name with result of running median
        :param step: (default = 10)

        """
        try:
            mf = mixture.GaussianMixtureFitting(
                    self.df["scale"].dropna()[::step],k=k)
        except KeyError:
            print("Column 'scale' is missing in data frame.\n"
                  "You must scale your data with coverage_scaling\n\n",
                  self.__doc__)
            return
        mf.estimate()
        self.gaussian = mf.results
        i = self._get_best_gaussian(mf.results)
        self.df[label] = (self.df["scale"] - mf.results["mus"][i]) / \
            mf.results["sigmas"][i]

    def get_low_coverage(self, threshold=-3, start=None, stop=None, 
            label="zscore"):
        """Keep position with zscore lower than INT and return a data frame.

        :param threshold: Integer
        :param start: Integer 
        :param stop: Integer
        """
        try:
            return self.df[start:stop].loc[self.df[label] < threshold]
        except KeyError:
            print("Column '" + label + "' is missing in data frame.\n"
                  "You must run compute_zscore before get low coverage.\n\n",
                  self.__doc__)

    def get_high_coverage(self, threshold=3, start=None, stop=None, 
            label="zscore"):
        """Keep position with zscore higher than INT and return a data frame.

        :param threshold: Integer
        :param start: Integer 
        :param stop: Integer
        """
        try:
            return self.df[start:stop].loc[self.df["zscore"] > threshold]
        except KeyError:
            print("Column '" + label + "' is missing in data frame.\n"
                  "You must run compute_zscore before get low coverage.\n\n",
                    self.__doc__)

    def _merge_row(self, start, stop):
        chrom = self.df["chr"][start]
        region = "{0} : {1}".format(start + 1, stop)
        cov = np.mean(self.df["cov"][start:stop])
        rm = np.mean(self.df["rm"][start:stop])
        zscore = np.mean(self.df["zscore"][start:stop])
        size = stop - start
        return {"chr": chrom, "region": region, "size": size, "mean_cov": cov, 
                "mean_rm": rm, "mean_zscore": zscore}

    def merge_region(self, df):
        """Merge position side by side of a data frame.
        """
        start = 0
        stop = 0
        merge_df = pd.DataFrame(columns=["chr", "region", "size", "mean_cov",
                                         "mean_rm", "mean_zscore"])
        for i, pos in enumerate(zip(df["pos"])):
            stop = pos[0]
            if(i == 0):
                start = pos[0]
                prev = pos[0]
                continue
            if(stop - 1 == prev):
                prev = stop
                continue
            else:
                merge_df = merge_df.append(self._merge_row(start - 1, prev),
                        ignore_index=True)
                start = stop
                prev = stop
        if(start < stop):
            merge_df = merge_df.append(self._merge_row(start - 1, prev),
                    ignore_index=True)
        return merge_df

    def plot_coverage(self, fontsize=16, filename=None, rm="rm"):
        """ Plot coverage as a function of position.

        """
        pylab.clf()
        self.df["cov"].plot(grid=True, color="b", label="coverage")
        self.df[rm].plot(grid=True, color="r", label="running median")
        pylab.legend(loc='best')
        pylab.xlabel("Position", fontsize=fontsize)
        pylab.ylabel("Coverage", fontsize=fontsize)
        try:
            pylab.tight_layout()
        except:
            pass
        if filename:
            pylab.savefig(filename)

    def plot_hist(self, fontsize=16, filename=None, label="zscore"):
        """ Barplot of zscore

        """
        pylab.clf()
        self.df[label].hist(grid=True, color="b", bins=50)
        pylab.xlabel("Z-Score", fontsize=fontsize)
        try:
            pylab.tight_layout()
        except:
            pass
        if filename:
            pylab.savefig(filename)

    def write_csv(self, filename, start=None, stop=None,
            labels=["pos", "cov", "rm"], header=True):
        """ Write CSV file of the dataframe.
            
        :param filename: csv filename.
        :param labels: list of index.
        :param header: boolean which determinate if the header is written.
        
        """
        try:
            self.df[labels][start:stop].to_csv(filename, header=header)
        except NameError:
            print("You must set the file name")
        except KeyError:
            print("Labels doesn't exist in the data frame")
