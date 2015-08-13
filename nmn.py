#!/usr/bin/env python2

from data.util import pp
from shape import *

import logging
from lasagne import init, layers, objectives, updates, nonlinearities
#import lasagne.layers.cuda_convnet
import numpy as np
import theano
import theano.tensor as T
import warnings


class Network:
  def __init__(self, l_input, l_output):
    self.l_input = l_input
    self.l_output = l_output

  def add_objective(self, input_type, output_type):
    params = layers.get_all_params(self.l_output)
    self.params = params

    t_input = input_type.make_input()
    t_output = layers.get_output(self.l_output, t_input)
    t_pred = T.argmax(t_output, axis=1)
    t_target = output_type.make_target()

    momentum = 0.9
    lr = 0.1

    t_loss = objectives.aggregate(output_type.loss(t_output, t_target))
    grads = T.grad(t_loss, params)
    scaled_grads, t_norm = updates.total_norm_constraint(grads, 1, return_norm=True)
    upd = updates.adadelta(scaled_grads, params, learning_rate = lr)

    loss_inputs = [t_input, t_target]
    self.loss = theano.function(loss_inputs, t_loss)
    self.train = theano.function(loss_inputs, t_loss, updates=upd)
    self.predict = theano.function([t_input], t_pred)
    self.response = theano.function([t_input], t_output)
    self.norm = theano.function(loss_inputs, t_norm)

class IdentityModule:
  def __init__(self):
    pass

  def instantiate(self, input, *below):
    assert len(below) == 1
    return below[0]

  def write_weights(self, dest, name):
    pass

class MinModule:
  def __init__(self):
    pass

  def instantiate(self, l_input, *below):
    l_min = layers.ElemwiseMergeLayer([b.l_output for b in below], T.minimum)
    l_threshold = layers.NonlinearityLayer(l_min)
    l_output = l_threshold
    return Network(l_input, l_output)

  def write_weights(self, dest, name):
    pass

class Conv1Module:
  def __init__(self, batch_size, channels, image_size, filter_count_1,
      filter_size_1, pool_size_1):
    self.batch_size = batch_size
    self.channels = channels
    self.image_size = image_size
    self.filter_count_1 = filter_count_1
    self.filter_size_1 = filter_size_1
    self.pool_size_1 = pool_size_1

    glorot = init.GlorotUniform()
    zero = init.Constant()
    self.w_conv1 = theano.shared(glorot.sample((filter_count_1, channels,
      filter_size_1, filter_size_1)))
    self.b_conv1 = theano.shared(zero.sample((filter_count_1,)))

  def instantiate(self, l_input, *below):

    if len(below) == 0:
      l_first = layers.InputLayer((self.batch_size, self.channels, self.image_size, self.image_size))
    else:
      l_first = layers.ConcatLayer([b.l_output for b in below], axis=1)

    l_conv1 = layers.Conv2DLayer(l_first, self.filter_count_1,
        self.filter_size_1,
        W=self.w_conv1, b=self.b_conv1, border_mode="same")
    if self.pool_size_1 > 1:
      l_pool1 = layers.MaxPool2DLayer(l_conv1, self.pool_size_1)
      l_1 = l_pool1
    else:
      l_1 = l_conv1

    l_output = l_1

    return Network(l_input, l_output)

  def write_weights(self, dest, name):
    np.save(dest + "/" + name, self.w_conv1.get_value())

class ConvModule:
  def __init__(self, batch_size, channels, image_size, filter_count_1,
      filter_count_2, filter_size_1, filter_size_2, pool_size_1, pool_size_2,
      tie=True):
    self.batch_size = batch_size
    self.channels = channels
    self.image_size = image_size
    self.filter_count_1 = filter_count_1
    self.filter_count_2 = filter_count_2
    self.filter_size_1 = filter_size_1
    self.filter_size_2 = filter_size_2
    self.pool_size_1 = pool_size_1
    self.pool_size_2 = pool_size_2
    self.tie = tie

    glorot = init.GlorotUniform()
    zero = init.Constant()
    if tie:
      self.w_conv1 = theano.shared(glorot.sample((filter_count_1, channels,
        filter_size_1, filter_size_1)))
      self.b_conv1 = theano.shared(zero.sample((filter_count_1,)))
      self.w_conv2 = theano.shared(glorot.sample((filter_count_2, filter_count_1,
        filter_size_2, filter_size_2)))
      self.b_conv2 = theano.shared(zero.sample((filter_count_2,)))
    else:
      self.w_conv1 = glorot
      self.w_conv2 = glorot
      self.b_conv1 = zero
      self.b_conv2 = zero

  def instantiate(self, l_input, *below):

    if len(below) == 0:
      #l_first = layers.InputLayer((self.batch_size, self.channels, self.image_size, self.image_size))
      assert False
    else:
      l_first = layers.ConcatLayer([b.l_output for b in below], axis=1)

    l_conv1 = layers.Conv2DLayer(l_first, self.filter_count_1,
        self.filter_size_1,
        W=self.w_conv1, b=self.b_conv1, border_mode="same")
    if self.pool_size_1 > 1:
      l_pool1 = layers.MaxPool2DLayer(l_conv1, self.pool_size_1)
      l_1 = l_pool1
    else:
      l_1 = l_conv1

    l_conv2 = layers.Conv2DLayer(l_1, self.filter_count_2, self.filter_size_2,
        W=self.w_conv2, b=self.b_conv2, border_mode="same")
    if self.pool_size_2 > 1:
      l_pool2 = layers.MaxPool2DLayer(l_conv2, self.pool_size_2)
      l_2 = l_pool2
    else:
      l_2 = l_conv2

    l_output = l_2

    return Network(l_input, l_output)

  def write_weights(self, dest, name):
    if self.tie:
      np.save(dest + "/" + name, self.w_conv1.get_value())

class MLPModule:

  def __init__(self, batch_size, input_size, hidden_size, output_size,
      output_nonlinearity=nonlinearities.rectify):
    self.batch_size = batch_size
    self.input_size = input_size
    self.hidden_size = hidden_size
    self.output_size = output_size

    self.output_nonlinearity = output_nonlinearity

    glorot = init.GlorotUniform()
    zero = init.Constant()
    self.w_hidden = theano.shared(glorot.sample((input_size, hidden_size)))
    self.b_hidden = theano.shared(zero.sample((hidden_size,)))
    self.w_output = theano.shared(glorot.sample((hidden_size, output_size)))
    self.b_output = theano.shared(zero.sample((output_size,)))

  def instantiate(self, l_input, *below):

    if len(below) == 0:
      #l_first = layers.InputLayer((self.batch_size, self.input_size))
      assert False
    else:
      l_first = layers.ConcatLayer([b.l_output for b in below])

    l_hidden = layers.DenseLayer(l_first, self.hidden_size, W=self.w_hidden,
            b=self.b_hidden)
            
    l_output = layers.DenseLayer(l_hidden, self.output_size, W=self.w_output,
            b=self.b_output, nonlinearity=self.output_nonlinearity)

    if self.output_nonlinearity != nonlinearities.softmax:
      l_shape = layers.ReshapeLayer(l_output, (self.batch_size, 1, 3, 3))
      l_out = l_shape
    else:
      l_out = l_output

    return Network(l_input, l_out)

  def write_weights(self, dest, name):
    pass

class NMN:
  def __init__(self, input_type, output_type, params):
    self.cached_networks = dict()
    self.input_type = input_type
    self.output_type = output_type

    self.modules = dict()
    #if "modules" in params:
    #  for key, mod_config in params["modules"].items():
    #    module = eval(mod_config)
    #    self.modules[key] = module

    self.module_builder = globals()[params["module_builder"]["class"]](params["module_builder"])

  def wire(self, query, l_input=None, l_pre=None):
    if l_input is None:
      assert l_pre is None
      l_input = self.get_input()
      l_pre = self.get_module("_pre", 1).instantiate(l_input)
    if not isinstance(query, tuple):
      return self.get_module(query, 1).instantiate(l_input, l_pre)
    args = [self.wire(q, l_input, l_pre) for q in query[1:]]
    return self.get_module(query[0], len(args)).instantiate(l_input, *args)

  def get_input(self):
    return self.module_builder.build_input()

  def get_module(self, name, arity):
    if name in self.modules:
      return self.modules[name]
    module = self.module_builder.build(name, arity)
    self.modules[name] = module
    return module

  def get_network(self, query):
    if query in self.cached_networks:
      return self.cached_networks[query]

    logging.debug('new network: %s', pp(query))
    pre_net = self.wire(query)
    net = self.get_module("_output", 1).instantiate(pre_net.l_input, pre_net)
    net.add_objective(self.input_type, self.output_type)

    self.cached_networks[query] = net
    return net

  def train(self, query, input_, output, return_norm=True):
    network = self.get_network(query)
    loss = network.train(input_, output)
    if return_norm:
      norm = network.norm(input_, output)
      return loss, norm
    else:
      return loss

  def loss(self, query, input_, output):
    network = self.get_network(query)
    return network.loss(input_, output)

  def predict(self, query, input_):
    network = self.get_network(query)
    return network.predict(input_)

  def response(self, query, input_):
    network = self.get_network(query)
    return network.response(input_)

  def serialize(self, dest):
    for name, module in self.modules.items():
      module.write_weights("weights", name)
