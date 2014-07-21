#!/usr/bin/env python
# encoding: utf-8
"""
analyze.py

Created by Benjamin Gross on 7.19.2014

Analysis of baseball salaries for Project 2 in the General Assembly
Data Science Course
"""

import argparse
import pandas
import numpy
import sys
import matplotlib.pyplot as plt
from sklearn import tree
from sklearn import ensemble
from sklearn import cluster
from sklearn import linear_model

#these seemed like the important columns, so I made the variable global
COLS = ['G_batting', 'AB', 'R', 'H', 'X2B', 'X3B', 'HR', 'RBI',
        'SB', 'CS', 'BB', 'SO', 'IBB', 'HBP', 'SH', 'SF', 'GIDP', 'teamID',
        'salary', 'yearID']

def year_based_significance_regression(file_path):
    """
    Run a year-based multivariate regression that uses only the significant variables
    as well as Random Forest Regression Trees to estimate the parameters

    Args:
    ------
    - file_path: string of the location of `baseball.csv`

    Returns:
    ---------
    - pandas.DataFrame of the in-sample and out-of-sample salary estimates
    """

    data = pandas.DataFrame.from_csv(file_path, index_col = None)
    data['age'] = data['yearID'] - data['birthYear']
    cols = COLS
    cols.append('age')
    all_data = data[cols].copy()
    all_data.dropna(inplace = True)
    teams = pandas.get_dummies(all_data['teamID'])
    x_cols = all_data.columns[map(lambda x: x not in ['teamID', 'salary'], all_data.columns)]
    xs = all_data[x_cols].join(teams)
    ys = all_data['salary']
    N = xs.shape[0]
    isi, in_sample, osi, out_sample = create_in_out_samples(xs, N/2)
    d = {}
    for year in all_data['yearID'].unique():
        no_yr = in_sample.columns.drop('yearID')
        d_too = {}
        is_yr = in_sample['yearID'] == year
        os_yr = out_sample['yearID'] == year
        ols = pandas.ols(x = in_sample.loc[is_yr, no_yr], y = ys[isi][is_yr])
        df = ols.summary_as_matrix
        is_sig = df.loc['p-value', df.loc['p-value', :] < .01].index

        if 'intercept' in is_sig:
            is_sig = is_sig.drop('intercept')

        clf = ensemble.RandomForestRegressor(n_estimators = 15)
        clf.fit(in_sample.loc[is_yr, is_sig], ys[isi][is_yr])
        print "For year " + str(year)
        is_score = clf.score(in_sample.loc[is_yr, is_sig], ys[isi][is_yr])
        print "in-sample" + '\t' + str(is_score)
        d_too['is-r2'] = is_score
        os_score = clf.score(out_sample.loc[os_yr, is_sig], ys[osi][os_yr])
        print "out-of-sample" + '\t' + str(os_score)
        d_too['os-r2'] = os_score
        d[year] = pandas.Series(d_too)

    return pandas.DataFrame(d).transpose()

def load_baseball_data(file_path):
    """
    Return a `pandas.DataFrame` of the baseball data

    Args:
    ------
    - file_path: the string location where `baseball.csv` is located

    Returns:
    --------
    `pandas.DataFrame` of the data

    """
    return pandas.DataFrame.from_csv(file_path, index_col = None)

def create_in_out_samples(data, in_sample_size):
    """
    Construct in-sample and out-of sample data

    Args:
    ------
    - data: `pandas.DataFrame` of the data
    - in_sample_size: integer of the size of the in-sample data (the
      out of sample data will be the rest of the data)

    Returns:
    --------
    - isi: `pandas.Index` of the in-sample data
    - in_sample: `pandas.DataFrame` of the in-sample data
    - osi: `pandas.Index` of the out-of-sample data
    - out_sample: `pandas.DataFrame` of the out-of-sample data, i.e.
      the rest of the data not part of the in_sample)
    """
    #in-sample index and out-of-sample index
    isi = numpy.random.choice(data.index, in_sample_size)
    osi = data.index[~data.index.isin(isi)]

    #create in-sample and out-of-sample DataFrames
    in_sample = data.loc[ isi, :].copy()
    out_sample = data.loc[ osi, :].copy()

    ##Fill the in-sample data with the means if there are nan values
    if in_sample.isnull().any().any():
        fill_data = in_sample.mean().apply(numpy.floor)
        in_sample.fillna( fill_data, inplace = True)

    #Fill the out-of-sample with the means from the in-sample
    if out_sample.isnull().any().any():
        out_sample.fillna( fill_data, inplace = True)

    return isi, in_sample, osi, out_sample

def mv_regression(xs, ys, in_sample_size):
    """
    Test a multi-variate regression creating the coefficients in sample
    and then using those coefficients to test the regression out of sample

    Args:
    -----
    - xs: `pandas.DataFrame` of the xs
    - ys: `pandas.Series` of the variable we're attempting to predit
    - in_sample_size: integer of the size of the `in sample` we want
      to use to train our regression

    Returns:
    ---------
    float of the MSE or Mean Squared Error

    """
    isi, in_sample, osi, out_sample = create_in_out_samples(xs, in_sample_size)

    #run the regression and predict the new values
    ols = pandas.ols(x = in_sample, y = ys[isi])
    betas = ols.beta
    intercept = betas['intercept']
    betas = betas[betas.index != 'intercept']

    #make our prediction on out of sample
    pred = out_sample.dot(betas) + intercept
    eps = (pred - ys[osi]).apply(numpy.abs)
    mse = eps.sum()/( eps.shape[0] - 2)

    return mse


def pc_regression(xs, ys, in_sample_size, var_target):
    """
    Construct a multivariate regression using the principal components
    that explain the var_target of variation

    Args:
    -----
    - xs: `pandas.DataFrame` of the xs
    - ys: `pandas.Series` of the variable we're attempting to predit
    - in_sample_size: integer of the size of the `in sample` we want
      to use to train our regression
    - var_target: a float of the proportion of variation that must
      be explained by the principal components

    Returns:
    ---------
    float of the MSE or Mean Squared Error

    """
    isi, in_sample, osi, out_sample = create_in_out_samples(xs, in_sample_size)

    #run the PCA
    u, s, v = numpy.linalg.svd(in_sample)
    prop_var = (s/s.sum()).cumsum()

    #choose the number of components that explain var_target variation
    n = (prop_var > var_target).argmax() + 1
    pc_xs = in_sample.dot(v[:, :n])
    ols = pandas.ols(x = pc_xs, y = ys[isi])
    intercept = ols.beta['intercept']
    betas = ols.beta
    betas = betas[betas.index != 'intercept']
    pc_os = out_sample.dot(v[:, :n])
    pred = pc_os.dot(betas) + intercept
    eps = (pred - ys[osi]).apply(numpy.abs)
    mse = eps.sum()/(eps.shape[0] - 2)

    return mse

def sklearn_mv_regression(xs, ys, in_sample_size):
    """
    Using `sklearn` Regression Trees

    Args:
    -----
    - xs: `pandas.DataFrame` of the xs
    - ys: `pandas.Series` of the variable we're attempting to predit
    - in_sample_size: integer of the size of the data to train the model on

    Returns:
    ---------
    float of the MSE or Mean Squared Error

    """
    d = {'MAE':[], 'in-sample-r2':[], 'out-sample-r2':[]}

    isi, in_sample, osi, out_sample = create_in_out_samples(xs, in_sample_size)
    clf = linear_model.LinearRegression(fit_intercept = True)
    clf.fit(in_sample, ys[isi])
    d['in-sample-r2'] = clf.score(in_sample, ys[isi])
    pred = clf.predict(out_sample, ys[osi])
    d['']

def regression_tree(xs, ys, max_depth, in_sample_size):
    """
    Using `sklearn` Regression Trees

    Args:
    -----
    - xs: `pandas.DataFrame` of the xs
    - ys: `pandas.Series` of the variable we're attempting to predit
    - max_depth: integer of the max depth of tree
    - in_sample_size: integer of the size of the data to train the model on

    Returns:
    ---------
    float of the MSE or Mean Squared Error

    """
    isi, in_sample, osi, out_sample = create_in_out_samples(xs, in_sample_size)
    clf = tree.DecisionTreeRegressor(max_depth = max_depth)

    clf.fit(in_sample, ys[isi])
    pred = clf.predict(out_sample)
    eps = (pred - ys[osi]).apply(numpy.abs)
    mse = eps.sum()/(eps.shape[0] - 2)
    return mse

def regression_forest(xs, ys, num_classifiers, in_sample_size):
    """
    Using `sklearn.ensemble` to create Random Forest Regression Trees

    Args:
    -----
    - xs: `pandas.DataFrame` of the xs
    - ys: `pandas.Series` of the variable we're attempting to predit
    - num_classifiers: The number of trees to use in the regression forest
    - in_sample_size: integer of the size of the data to train the model on

    Returns:
    ---------
    float of the MSE or Mean Squared Error


    """
    isi, in_sample, osi, out_sample = create_in_out_samples(xs, in_sample_size)
    clf = ensemble.RandomForestRegressor(num_classifiers)
    clf.fit(in_sample, ys[isi])
    pred = clf.predict(out_sample)
    eps = (pred - ys[osi]).apply(numpy.abs)
    mse = eps.sum()/(eps.shape[0] - 2)
    return mse

def cluster_then_forest(xs, ys, in_sample_size):
    isi, in_sample, osi, out_sample = create_in_out_samples(xs, in_sample_size)
    clf = cluster.KMeans(n_clusters = 4)
    clf.fit(in_sample)
    oos_clusterid = clf.predict(out_sample)
    ins_clusterid = clf.predict(in_sample)

    for id in numpy.unique(oos_clusterid):
        print "Now working on Cluster " + str(id)
        oos_ind = oos_clusterid == id
        ins_ind = ins_clusterid == id

        tree = ensemble.RandomForestRegressor(50)

        tree.fit(in_sample[ins_ind], ys[isi][ins_ind])
        print "Score for in-sample"
        print str(tree.score(in_sample[ins_ind], ys[isi][ins_ind]))

        print "Score for out-of sample"
        tree.predict(out_sample[oos_ind])
        print str(tree.score(out_sample[oos_ind], ys[osi][oos_ind]))

    return None



def compare_functions(xs, ys, num_sims, in_sample_size):
    """
    An aggregation function that generates num_sims simulations of
    random sample size `in_sample_size` and returns a `pandas.DataFrame`
    of the MSE for each of the functions

    Args:
    ------
    - num_sims: The number of times you would like to run the sampling
      exercise
    - in_sample_size: The integer size of the in-sample data

    Returns:
    --------
    `pandas.DataFrame` of the different MSE for each of the functions
    """

    d = {'mv_regression':[],
         'pc_regression': [],
         'regression_tree':[],
         'regression_forest':[]}

    for i in numpy.arange(num_sims):
        print "Currently on " + str(i) + " of " + str(num_sims)

        d['mv_regression'].append( mv_regression(xs, ys,
                                    in_sample_size = in_sample_size) )
        d['pc_regression'].append( pc_regression(xs, ys,
                                    in_sample_size = in_sample_size,
                                    var_target = .9) )
        d['regression_tree'].append( regression_tree(xs, ys,
                                    max_depth = 4,
                                    in_sample_size = in_sample_size) )
        d['regression_forest'].append( regression_forest(xs, ys,
                                    num_classifiers = 15,
                                    in_sample_size = in_sample_size) )

    return pandas.DataFrame(d)

if __name__ == '__main__':

	usage = sys.argv[0] + "usage instructions"
	description = "This is my silly little analyze function"
	parser = argparse.ArgumentParser(description = description, usage = usage)
	parser.add_argument('name_1', nargs = 1, type = str, help = 'describe input 1')
	parser.add_argument('name_2', nargs = '+', type = int, help = "describe input 2")

	args = parser.parse_args()

	script_function(input_1 = args.name_1[0], input_2 = args.name_2)
