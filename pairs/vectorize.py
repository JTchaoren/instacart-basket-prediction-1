#!/usr/bin/env python
import argparse
import logging
import scipy.sparse
import numpy as np

from baskets import common, constants, user_wrapper
from baskets.user_wrapper import iterate_wrapped_users
from baskets.time_me import time_me
import baskets.time_me

import count_pairs
from user_helpers import paired_pids

def save_fold(fold, X, y):
  xpath = 'x_{}.npz'.format(fold)
  ypath = 'y_{}.npy'.format(fold)
  scipy.sparse.save_npz(xpath, X)
  np.save(ypath, y)

def load_fold(fold):
  xpath = 'x_{}.npz'.format(fold)
  ypath = 'y_{}.npy'.format(fold)
  X = scipy.sparse.load_npz(xpath)
  y = np.load(ypath)
  return X, y
  
def vectorize(users, pair_lookup, logits=None):
  indptrs = [0]
  indices = []
  labels = []
  for user in users:
    order = user.orders[-1]
    orderpids = set(order.products)
    for pid in user.sorted_pids:
      label = pid in orderpids
      labels.append(label)
      # (now-silly variable name)
      prevs = paired_pids(user, pid)

      # TODO: May want to normalize prevs to sum to 1? 
      # Or maybe not actually.
      prev_indices = [ (constants.N_PRODUCTS + pair_lookup[(pid, otherpid)])
          for otherpid in prevs
          if (pid, otherpid) in pair_lookup ]
      focal_ix = pid-1
      row_indices = [focal_ix] + prev_indices

      # extra index for boost logit
      row_indices = [0] + [i+1 for i in row_indices]

      indices += row_indices
      indptrs.append( len(indices) )

  nrows = len(indptrs) - 1
  nprods = constants.N_PRODUCTS
  nfeats = nprods + len(pair_lookup)
  X_shape = (nrows, nfeats)
  dat = np.ones( len(indices), dtype=np.float32)
  logit_indices = indptrs[:-1]
  if logits:
    dat[logit_indices] = logits
  else:
    dat[logit_indices] = 0
  X = scipy.sparse.csr_matrix( (dat, indices, indptrs), shape=X_shape )
  return X, np.array(labels, dtype=int)


def main():
  baskets.time_me.set_default_mode('print')
  logging.basicConfig(level=logging.INFO)
  parser = argparse.ArgumentParser()
  parser.add_argument('folds', nargs='+')
  parser.add_argument('-b', '--boost', help='Tag of model to boost from')
  args = parser.parse_args()

  with time_me('Loaded pair lookup'):
    lookup = count_pairs.load_pair_lookup()
  for fold in args.folds:
    users = iterate_wrapped_users(fold)
    if args.boost:
      logits = user_wrapper.logits_for_tag(args.boost, fold)
    else:
      logits = None
    with time_me('Vectorized'):
      X, y = vectorize(users, lookup, logits)
    logging.info('Loaded X with shape {} and y with shape {}'.format(
      X.shape, y.shape))
    logging.info('Mean # of non-zero features per instance = {:.1f}'.format(
      X.sum(axis=1).mean()
      ))
    save_fold(fold, X, y)

if __name__ == '__main__':
  with time_me(mode='print'):
    main()
