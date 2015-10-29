#!/usr/bin/env python2

from util import *

import cairo
import itertools
import logging
import logging.config
import numpy as np
import yaml

#N_QUERY_INSTS = 2048
N_QUERY_INSTS = 64

N_TRAIN_TINY  = 10
N_TRAIN_SMALL = 100
N_TRAIN_MED   = 1000
N_TRAIN_LARGE = 10000
N_TRAIN_ALL   = N_TRAIN_MED

N_TEST        = 1000
N_VAL         = 1000

SHAPE_CIRCLE = 0
SHAPE_SQUARE = 1
SHAPE_TRIANGLE = 2
N_SHAPES = SHAPE_TRIANGLE + 1
SHAPE_STR = {0: "circle", 1: "square", 2: "triangle"}

SIZE_SMALL = 0
SIZE_BIG = 1
N_SIZES = SIZE_BIG + 1
SIZE_STR = {0: "small", 1: "big"}

COLOR_RED = 0
COLOR_GREEN = 1
COLOR_BLUE = 2
N_COLORS = COLOR_BLUE + 1
COLOR_STR = {0: "red", 1: "green", 2: "blue"}

BOOL_STR = {True: "true", False: "false"}

WIDTH = 30
HEIGHT = 30

N_CELLS = 3

CELL_WIDTH = WIDTH / N_CELLS
CELL_HEIGHT = HEIGHT / N_CELLS

BIG_RADIUS = CELL_WIDTH * .75 / 2
SMALL_RADIUS = CELL_WIDTH * .5 / 2

GRAMMAR = {
  "$Q": [
    Rule("$Q", ("count", "$S"), 1),
    Rule("$Q", ("shape", "$S"), 2),
    Rule("$Q", ("color", "$S"), 2),
    Rule("$Q", ("size", "$S"), 2),
  ],
  "$S": [
    Rule("$S", ("next_to", "$S"), 1),
    Rule("$S", ("left_of", "$S"), 1),
    Rule("$S", ("right_of", "$S"), 1),
    Rule("$S", ("above", "$S"), 1),
    Rule("$S", ("below", "$S"), 1),
    Rule("$S", ("or", "$S", "$S"), 1),
    Rule("$S", ("and", "$S", "$S"), 1),
    Rule("$S", ("xor", "$S", "$S"), 1),
    Rule("$S", "small", 1),
    Rule("$S", "big", 1),
    Rule("$S", "red", 1),
    Rule("$S", "green", 1),
    Rule("$S", "blue", 1),
    Rule("$S", "circle", 1),
    Rule("$S", "square", 1),
    Rule("$S", "triangle", 1),
    Rule("$S", "nothing", 1)
  ]
}

def draw(shape, color, size, left, top, ctx):
  center_x = (left + .5) * CELL_WIDTH
  center_y = (top + .5) * CELL_HEIGHT

  radius = SMALL_RADIUS if size == SIZE_SMALL else BIG_RADIUS
  radius *= (.9 + np.random.random() * .2)

  if color == COLOR_RED:
    rgb = np.asarray([1., 0., 0.])
  elif color == COLOR_GREEN:
    rgb = np.asarray([0., 1., 0.])
  else:
    rgb = np.asarray([0., 0., 1.])
  rgb += (np.random.random(size=(3,)) * .4 - .2)
  rgb = np.clip(rgb, 0., 1.)

  #rgb = np.asarray([1., 1., 1.])

  if shape == SHAPE_CIRCLE:
    ctx.arc(center_x, center_y, radius, 0, 2*np.pi)
  elif shape == SHAPE_SQUARE:
    ctx.new_path()
    ctx.move_to(center_x - radius, center_y - radius)
    ctx.line_to(center_x + radius, center_y - radius)
    ctx.line_to(center_x + radius, center_y + radius)
    ctx.line_to(center_x - radius, center_y + radius)
  else:
    ctx.new_path()
    ctx.move_to(center_x - radius, center_y + radius)
    ctx.line_to(center_x, center_y - radius)
    ctx.line_to(center_x + radius, center_y + radius)
  ctx.set_source_rgb(*rgb)
  ctx.fill()

class Image:
  def __init__(self, shapes, colors, sizes, data, cheat_data = None):
    self.shapes = shapes
    self.colors = colors
    self.sizes = sizes
    self.data = data
    self.cheat_data = cheat_data

def sample_image():
  data = np.zeros((WIDTH, HEIGHT, 4), dtype=np.uint8)
  cheat_data = np.zeros((6, 3, 3))
  surf = cairo.ImageSurface.create_for_data(data, cairo.FORMAT_ARGB32, WIDTH, HEIGHT)
  ctx = cairo.Context(surf)
  ctx.set_source_rgb(0., 0., 0.)
  ctx.paint()

  shapes = [[None for c in range(3)] for r in range(3)]
  colors = [[None for c in range(3)] for r in range(3)]
  sizes = [[None for c in range(3)] for r in range(3)]

  for r in range(3):
    for c in range(3):
      if np.random.random() < 0.2:
        continue
      shape = np.random.randint(N_SHAPES)
      color = np.random.randint(N_COLORS)
      size = np.random.randint(N_SIZES)
      draw(shape, color, size, c, r, ctx)
      shapes[r][c] = shape
      colors[r][c] = color
      sizes[r][c] = size
      cheat_data[shape][r][c] = 1
      cheat_data[N_SHAPES + color][r][c] = 1

  #surf.write_to_png("_sample.png")
  return Image(shapes, colors, sizes, data, cheat_data)

def evaluate(query, image):
  # forgive me
  if isinstance(query, tuple):
    head = query[0].replace("-", "")
    a1 = evaluate(query[1], image)
    a2 = evaluate(query[2], image) if len(query) > 2 else None
    if a1 is None:
      return None
    a1 = list(a1)
    a2 = list(a2) if a2 is not None else None

    shapes = [image.shapes[ax][ay] for ax, ay in a1]
    shapes = [s for s in shapes if s is not None]
    n_shapes = len(set(shapes))

    colors = [image.colors[ax][ay] for ax, ay in a1]
    colors = [c for c in colors if c is not None]
    n_colors = len(set(colors))

    sizes = [image.sizes[ax][ay] for ax, ay in a1]
    sizes = [s for s in sizes if s is not None]

    if head == "count":
      return len(a1)
    elif head == "shape":
      return SHAPE_STR[shapes[0]] if len(set(shapes)) == 1 else None
    elif head == "color":
      return COLOR_STR[colors[0]] if len(set(colors)) == 1 else None
    elif head == "size":
      return SIZE_STR[sizes[0]] if len(set(sizes)) == 1 else None
    elif head == "left_of":
      return set([(r,c-1) for r,c in a1 if c > 0])
    elif head == "right_of":
      return set([(r,c+1) for r,c in a1 if c < N_CELLS-1])
    elif head == "next_to":
      return set([(r,c-1) for r,c in a1 if c > 0] + [(r,c+1) for r,c in a1 if c < N_CELLS-1])
    elif head == "above":
      return set([(r-1,c) for r,c in a1 if r > 0])
    elif head == "below":
      return set([(r+1,c) for r,c in a1 if r < N_CELLS-1])

    elif head == "is_red":
      return BOOL_STR[set(colors) == {COLOR_RED}] if n_colors == 1 else None
    elif head == "is_green":
      return BOOL_STR[set(colors) == {COLOR_GREEN}] if n_colors == 1 else None
    elif head == "is_blue":
      return BOOL_STR[set(colors) == {COLOR_BLUE}] if n_colors == 1 else None
    elif head == "is_circle":
      return BOOL_STR[set(shapes) == {SHAPE_CIRCLE}] if n_shapes == 1 else None
    elif head == "is_square":
      return BOOL_STR[set(shapes) == {SHAPE_SQUARE}] if n_shapes == 1 else None
    elif head == "is_triangle":
      return BOOL_STR[set(shapes) == {SHAPE_TRIANGLE}] if n_shapes == 1 else None

    if a2 == None:
      return None

    elif head == "and":
      return set(a1) & set(a2)
    elif head == "or":
      return set(a1) | set(a2)
    elif head == "xor":
      return set(a1) ^ set(a2)

    elif head == "is":
      if len(a1) == 0: return None
      return BOOL_STR[len(set(a1) & set(a2)) > 0]

  else:
    query = query.replace("-", '')
    if query == "small":
      return set([(r,c) for r in range(N_CELLS) for c in range(N_CELLS) if image.sizes[r][c] == SIZE_SMALL])
    elif query == "big":
      return set([(r,c) for r in range(N_CELLS) for c in range(N_CELLS) if image.sizes[r][c] == SIZE_BIG])
    elif query == "red":
      return set([(r,c) for r in range(N_CELLS) for c in range(N_CELLS) if image.colors[r][c] == COLOR_RED])
    elif query == "green":
      return set([(r,c) for r in range(N_CELLS) for c in range(N_CELLS) if image.colors[r][c] == COLOR_GREEN])
    elif query == "blue":
      return set([(r,c) for r in range(N_CELLS) for c in range(N_CELLS) if image.colors[r][c] == COLOR_BLUE])
    elif query == "circle":
      return set([(r,c) for r in range(N_CELLS) for c in range(N_CELLS) if image.shapes[r][c] == SHAPE_CIRCLE])
    elif query == "square":
      return set([(r,c) for r in range(N_CELLS) for c in range(N_CELLS) if image.shapes[r][c] == SHAPE_SQUARE])
    elif query == "triangle":
      return set([(r,c) for r in range(N_CELLS) for c in range(N_CELLS) if image.shapes[r][c] == SHAPE_TRIANGLE])
    elif query == "nothing":
      return set([(r,c) for r in range(N_CELLS) for c in range(N_CELLS) if image.shapes[r][c] is None])

  return None

def gen_sent(query):
  if query in ("red", "green", "blue"):
    return query + " objects"
  if query in ("circle", "square", "triangle"):
    return query + "s"
  if query[0] == "is":
    return "are the " + gen_sent(query[1]) + " " + gen_sent(query[2])
  if query[0] == "shape":
    return "what shapes are " + gen_sent(query[1])
  if query[0] == "color":
    return "what colors are " + gen_sent(query[1])
  if query[0] in ("left_of", "right_of", "above", "below"):
    return query[0].replace("_", " ") + " " + gen_sent(query[1])

def gen_sentences(query):
  generated = gen_sent(query)
  print generated
  return [generated] * N_QUERY_INSTS

def gen_images(query):
  sent = gen_sent(query)
  data = []
  results = set()
  i = 0
  while i < N_QUERY_INSTS * 5 and len(data) < N_QUERY_INSTS:
    i += 1
    image = sample_image()
    result = evaluate(query, image)
    #print query
    #print 'shapes', image.shapes
    #print 'colors', image.colors
    #print 'sizes', image.sizes
    #print result
    #print
    #for channel in range(4):
    #  for r in range(30):
    #    for c in range(30):
    #      #print "%2d" % (image.data[r,c,channel] / 255. * 10),
    #      print "#" if image.data[r,c,channel] > 128 else ".",
    #    print
    #  print
    #print "==="
    if result is not None and result != 0:
      data.append((sent, query, image, result))
      results.add(result)

  if len(data) == N_QUERY_INSTS: # and len(results) > 1:
    return data
  else:
    return None

if __name__ == "__main__":
  #with open("../log.yaml") as log_config_f:
  #  logging.config.dictConfig(yaml.load(log_config_f))

  seen = set()
  train_data = []
  val_data = []
  test_data = []

  train_text = []
  val_text = []

  # shape, color | circle, square, triangle, red, green, blue
  tops = ['shape', 'color'] # , 'size']
  #tops = ['is_red', 'is_green', 'is_blue', 'is_circle', 'is_square', 'is_triangle']
  #tprime = sum([[t, t+"-", t+'--'] for t in tops], [])
  tprime = tops

  mids = ['above', 'below', 'left_of', 'right_of']
  #mprime = sum([[m, m+"-", m+'--'] for m in mids], [])
  mprime = mids

  bottoms = ['red', 'green', 'blue', 'circle', 'square', 'triangle'] # big small
  #bottoms = ["red", "green", "blue"]
  #bprime = sum([[t, t+"-", t+'--'] for t in bottoms], [])
  bprime = bottoms

  queries2 = [("is",) + l for l in itertools.product(bprime, bprime)]
  queries3 = list(itertools.product(bprime, mprime, bprime))
  queries3 = [("is", q[0], (q[1], q[2])) for q in queries3]
  queries = queries2 + queries3

  #queries2 = [(t, b) for t, b in itertools.product(tprime, bprime)]
  #queries3 = list(itertools.product(["red", "green", "blue"], ["circle", "square", "triangle"]))
  #queries3 = [("is", q[0], q[1]) for q in queries3]
  #queries4 = list(itertools.product(tprime, mprime, bprime))
  #queries4 = [(q[0], (q[1], q[2])) for q in queries4]
  #queries = queries2 + queries3 + queries4

  np.random.shuffle(queries)

  from collections import defaultdict
  projections = defaultdict(list)

  for query in queries:
    proj = pp(query).replace("-", "")
    projections[proj].append(query)

  pk = projections.keys()
  np.random.shuffle(pk)
  train_queries = sum([projections[p] for p in pk[:-16]], [])
  val_queries = sum([projections[p] for p in pk[-16:]], [])

  #train_queries = queries[:-36]
  #val_queries = queries[-36:]

  #train_queries = queries
  #val_queries = queries

  #train_queries = [
  #  ('shape', 'circle'),
  #  ('shape', 'square'),
  #  ('shape', 'triangle'),
  #  ('shape', 'red'),
  #  ('shape', 'blue'),
  #  ('color', 'circle'),
  #  ('color', 'triangle'),
  #  ('color', 'red'),
  #  ('color', 'green'),
  #  ('color', 'blue')
  #]

  #val_queries = [
  #  ('shape', 'green'),
  #  ('color', 'square'),
  #]

  for query in train_queries:
    print pp(query)
    images = gen_images(query)
    #assert images is not None
    if images is None:
      logging.warn("excluding %s", pp(query))
      continue
    train_data += images

  print "--"

  for query in val_queries:
    print pp(query)
    images = gen_images(query)
    if images is None:
        logging.warn("excluding %s", pp(query))
        continue
    val_data += images

 # while len(train_data) < N_TRAIN_ALL * N_QUERY_INSTS:
 #   query = sample("$Q", GRAMMAR)
 #   if query not in seen:
 #     images = gen_images(query)
 #     if images is not None:
 #       train_data += images
 #       seen.add(query)
 #       if len(train_data) % (1000 * N_QUERY_INSTS) == 0:
 #         logging.debug("%d / %d", len(train_data) / N_QUERY_INSTS, N_TRAIN_ALL)


 # logging.debug("generated train")
 # train_data_tiny = train_data[:N_TRAIN_TINY * N_QUERY_INSTS]
 # train_data_small = train_data[:N_TRAIN_SMALL * N_QUERY_INSTS]
 # train_data_med = train_data[:N_TRAIN_MED * N_QUERY_INSTS]
 # train_data_large = train_data

 # while len(val_data) < N_VAL * N_QUERY_INSTS:
 #   query = sample("$Q", GRAMMAR)
 #   if query not in seen:
 #     images = gen_images(query)
 #     if images is not None:
 #       val_data += images
 #       seen.add(query)
 # logging.debug("generated val")

 # while len(test_data) < N_TEST * N_QUERY_INSTS:
 #   query = sample("$Q", GRAMMAR)
 #   if query not in seen:
 #     images = gen_images(query)
 #     if images is not None:
 #       test_data += images
 #       seen.add(query)
 # logging.debug("generated test")

  train_data_tiny = train_data[:N_TRAIN_TINY * N_QUERY_INSTS]
  train_data_small = train_data[:N_TRAIN_SMALL * N_QUERY_INSTS]
  train_data_med = train_data[:N_TRAIN_MED * N_QUERY_INSTS]
  train_data_large = train_data

  sets = {
    "train.tiny": train_data_tiny,
    "train.small": train_data_small,
    "train.med": train_data_med,
    "train.large": train_data_large,
    "val": val_data,
    "test": test_data
  }

  for set_name, set_data in sets.items():

    set_inputs = np.asarray([image.data[:,:,0:3] for sent, query, image, result in set_data])
    np.save("shapes/%s.input" % set_name, set_inputs)
    #image_data = image.data
    #image_data = image_data[:,:,0:3].flatten().tolist()
    #print >>input_f, " ".join([str(v) for v in image_data])

    with open("shapes/%s.query" % set_name, "w") as query_f, \
         open("shapes/%s.output" % set_name, "w") as output_f, \
         open("shapes/%s.txt" % set_name, "w") as string_f:
         #open("shapes/%s.input" % set_name, "w") as input_f, \
      for sent, query, image, result in set_data:
        str_query = pp(query)
        print >>string_f, sent
        print >>query_f, str_query
        print >>output_f, result


        #image_data = image.cheat_data.flatten().tolist()
        #print >>input_f, " ".join([str(v) for v in image_data])
