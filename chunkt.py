#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import sys
import json
import copy
import codecs
import hashlib
import markdown
import scipy.stats as st

from jinja2 import Template
from bs4 import BeautifulSoup
from collections import deque
from datetime import datetime
from markdown.extensions.codehilite import CodeHiliteExtension
from flask import Flask, render_template, request, redirect, url_for

reload(sys)
sys.setdefaultencoding('utf8')

################################################################################
# CONSTANTS
################################################################################

ROOT_DIR = '/home/caio/Dropbox/knods/'
CHUNKTFILE = ROOT_DIR + 'chunktfile.json'
DATE_FORMAT = '%Y-%m-%dT%H:%M:%S'
LAST_N = 2
COMPLETION_HALF_LIFE = 30.0
PULL_HALF_LIFE = 30.0
HITS_TO_COMPLETE = 2

################################################################################
# TEMPLATES
################################################################################

INDEX_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
    <head>
        <title>chunkt</title>
        <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.5/css/bootstrap.min.css">
        <script src="//code.jquery.com/jquery-1.11.3.min.js"></script>
        <script src="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.5/js/bootstrap.min.js"></script>
        <style>
            body { background: url(http://subtlepatterns.com/patterns/cubes.png); }
            .container-fluid { margin: 10px !important; }
            .list-group { margin-bottom: 10px; !important; }
            .completed { float: right; }
        </style>
    <head>
    <body style="background: url(http://subtlepatterns.com/patterns/cubes.png);">
        <div class="container-fluid">
            <div class="row">
                <div class="panel panel-primary">
                    <div class="panel-heading">
                        <h1 class="panel-title"><strong>chunkt</strong></h1>
                    </div>
                    <div class="panel-body">
                        <div id="documents" class="list-group">
                        {% for document in documents %}
                            <a href="/{{ document.hash }}/pull" class="list-group-item">
                                {{ ' / '.join(document.path.split('/')) }}
                                <span class="badge completed">
                                    {{ bandit_engine.completed(document) }} %
                                </span>
                            </a>
                        {% endfor %}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </body>
</html>'''

CHUNK_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
    <head>
        <title>chunkt</title>
        <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.5/css/bootstrap.min.css">
        <script src="//code.jquery.com/jquery-1.11.3.min.js"></script>
        <script src="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.5/js/bootstrap.min.js"></script>
        <script type="text/javascript" src="https://cdnjs.cloudflare.com/ajax/libs/mathjax/2.7.1/MathJax.js?config=TeX-AMS-MML_HTMLorMML"></script>
        <script>
            MathJax.Hub.Config({ tex2jax: { inlineMath: [['$','$']] }} );
            $(function() {
                $("#show").on('click', function() {
                    $(".action-btn-group, .back").toggleClass('hide');
                    $("#reward1").focus()
                }).focus();
                $(".reward").on('click', function() {
                    var rewardValue = $(this).attr('data-value');
                    $("#reward-form [name=value]").attr('value', rewardValue);
                    $("#reward-form").submit();
                });
            });
        </script>
        <style>
            body { background: url(http://subtlepatterns.com/patterns/cubes.png); }
            .container-fluid { margin: 10px !important; }
            .completed { float: right; }

            .hll { background-color: #ffffcc }
            .c { color: #408080; font-style: italic } /* Comment */
            .err { border: 1px solid #FF0000 } /* Error */
            .k { color: #008000; font-weight: bold } /* Keyword */
            .o { color: #666666 } /* Operator */
            .cm { color: #408080; font-style: italic } /* Comment.Multiline */
            .cp { color: #BC7A00 } /* Comment.Preproc */
            .c1 { color: #408080; font-style: italic } /* Comment.Single */
            .cs { color: #408080; font-style: italic } /* Comment.Special */
            .gd { color: #A00000 } /* Generic.Deleted */
            .ge { font-style: italic } /* Generic.Emph */
            .gr { color: #FF0000 } /* Generic.Error */
            .gh { color: #000080; font-weight: bold } /* Generic.Heading */
            .gi { color: #00A000 } /* Generic.Inserted */
            .go { color: #888888 } /* Generic.Output */
            .gp { color: #000080; font-weight: bold } /* Generic.Prompt */
            .gs { font-weight: bold } /* Generic.Strong */
            .gu { color: #800080; font-weight: bold } /* Generic.Subheading */
            .gt { color: #0044DD } /* Generic.Traceback */
            .kc { color: #008000; font-weight: bold } /* Keyword.Constant */
            .kd { color: #008000; font-weight: bold } /* Keyword.Declaration */
            .kn { color: #008000; font-weight: bold } /* Keyword.Namespace */
            .kp { color: #008000 } /* Keyword.Pseudo */
            .kr { color: #008000; font-weight: bold } /* Keyword.Reserved */
            .kt { color: #B00040 } /* Keyword.Type */
            .m { color: #666666 } /* Literal.Number */
            .s { color: #BA2121 } /* Literal.String */
            .na { color: #7D9029 } /* Name.Attribute */
            .nb { color: #008000 } /* Name.Builtin */
            .nc { color: #0000FF; font-weight: bold } /* Name.Class */
            .no { color: #880000 } /* Name.Constant */
            .nd { color: #AA22FF } /* Name.Decorator */
            .ni { color: #999999; font-weight: bold } /* Name.Entity */
            .ne { color: #D2413A; font-weight: bold } /* Name.Exception */
            .nf { color: #0000FF } /* Name.Function */
            .nl { color: #A0A000 } /* Name.Label */
            .nn { color: #0000FF; font-weight: bold } /* Name.Namespace */
            .nt { color: #008000; font-weight: bold } /* Name.Tag */
            .nv { color: #19177C } /* Name.Variable */
            .ow { color: #AA22FF; font-weight: bold } /* Operator.Word */
            .w { color: #bbbbbb } /* Text.Whitespace */
            .mb { color: #666666 } /* Literal.Number.Bin */
            .mf { color: #666666 } /* Literal.Number.Float */
            .mh { color: #666666 } /* Literal.Number.Hex */
            .mi { color: #666666 } /* Literal.Number.Integer */
            .mo { color: #666666 } /* Literal.Number.Oct */
            .sb { color: #BA2121 } /* Literal.String.Backtick */
            .sc { color: #BA2121 } /* Literal.String.Char */
            .sd { color: #BA2121; font-style: italic } /* Literal.String.Doc */
            .s2 { color: #BA2121 } /* Literal.String.Double */
            .se { color: #BB6622; font-weight: bold } /* Literal.String.Escape */
            .sh { color: #BA2121 } /* Literal.String.Heredoc */
            .si { color: #BB6688; font-weight: bold } /* Literal.String.Interpol */
            .sx { color: #008000 } /* Literal.String.Other */
            .sr { color: #BB6688 } /* Literal.String.Regex */
            .s1 { color: #BA2121 } /* Literal.String.Single */
            .ss { color: #19177C } /* Literal.String.Symbol */
            .bp { color: #008000 } /* Name.Builtin.Pseudo */
            .vc { color: #19177C } /* Name.Variable.Class */
            .vg { color: #19177C } /* Name.Variable.Global */
            .vi { color: #19177C } /* Name.Variable.Instance */
            .il { color: #666666 } /* Literal.Number.Integer.Long */
        </style>
    <head>
    <body style="background: url(http://subtlepatterns.com/patterns/cubes.png);">
        <div class="container-fluid">
            <div class="row">
                <div class="panel panel-primary">
                    <div class="panel-heading">
                        <h1 class="panel-title"><a href="/" tabindex="-1">
                            <strong>chunkt</strong></a> <em>/ {{ ' / '.join(document.path.split('/')) }}</em>
                            <span class="completed badge">
                                {{ bandit_engine.completed(document) }} %
                            </span>
                        </h1>
                    </div>
                    <div class="panel-body">
                        <ol class="front breadcrumb">
                            {% for front_content in chunk.front() %}
                                <li class="active">{{ front_content }}</li>
                            {% endfor %}
                        </ol>
                        <ul class="back list-group hide">
                        {% for child_content in chunk.back() %}
                            <li class="list-group-item">{{ child_content }}</li>
                        {% endfor %}
                        </ul>
                        <div class="action-btn-group btn-group btn-group-justified" role="group">
                            <div class="btn-group" role="group">
                                <button id="show" type="button" class="btn btn-default">
                                    <span class="glyphicon glyphicon-plus" aria-hidden="true"></span>
                                </button>
                            </div>
                        </div>
                        <div class="action-btn-group btn-group btn-group-justified hide" role="group">
                            <div class="btn-group" role="group">
                                <button id="reward1" type="button" data-value="1" class="reward btn btn-default">
                                    <span class="glyphicon glyphicon-remove" aria-hidden="true"></span>
                                </button>
                            </div>
                            <div class="btn-group" role="group">
                                <button id="reward0" type="button" data-value="0" class="reward btn btn-default">
                                    <span class="glyphicon glyphicon-ok" aria-hidden="true"></span>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <form id="reward-form" class="hide" method="post" action="/{{ document.hash }}/reward">
            <input type="hidden" name="document_hash" value="{{ document.hash }}" />
            <input type="hidden" name="chunk_hash" value="{{ chunk.hash() }}" />
            <input type="hidden" name="value" value="0" />
        </form>
    </body>
</html>'''

################################################################################
# APP
################################################################################

app = Flask(__name__)

################################################################################
# CHUNK
################################################################################

class Chunk:

    def __init__(self, el, parent, registry, func=None, depth=0):
        self.depth = depth
        self.parent = parent
        self.children = []
        self.el = el

        matched = el and el.name and re.match('[hH]([0-9])', el.name)

        if matched:
            self._handle_titles(el, registry, func, matched)
        elif el.name == 'li':
            self._handle_list_items(el, registry, func)
        elif el.name == 'pre':
            if el.find_parent('.codehilite'):
                self.content = str(el.parent)
            else:
                self.content = str(el)

        if func:
            func(self, registry)

    def _handle_titles(self, el, registry, func, matched):
        level = int(matched.group(1))
        self.content = el.renderContents()

        for sibling in el.next_siblings:
            if not sibling or not sibling.name:
                continue

            s_matched = re.match('[hH]([0-9])', sibling.name)
            s_level = s_matched and int(s_matched.group(1))
            if s_matched and s_level > level:
                self.children.append(Chunk(sibling, self, registry, func=func, depth=self.depth+1))
            elif s_matched and s_level <= level:
                break

        if len(self.children) > 0:
            return

        uls = el.select('~ ul')
        if not uls:
            return

        for li in uls[0].select('> li'):
            if li.name:
                self.children.append(Chunk(li, self, registry, func=func, depth=self.depth+1))

    def _handle_list_items(self, el, registry, func):
        p = el.select('> p')
        ul = el.select('> ul')
        pre = el.select('> pre')
        wrapped_pre = el.select('> .codehilite > pre')

        if p and not ul:
            self.content = p[0].renderContents()
        elif not p and not ul and not wrapped_pre:
            self.content = el.renderContents()
        elif ul:
            self.content = self._extract_list_item_content(el)
            for li in ul[0].select('> li'):
                if li.name:
                    self.children.append(Chunk(li, self, registry, func=func, depth=self.depth+1))

        self.content = self._extract_list_item_content(el)

        if len(self.children) > 0:
            return

        code = pre or wrapped_pre
        if code:
            self.children.append(Chunk(code[0], self, registry, func=func, depth=self.depth+1))

    def _extract_list_item_content(self, el):
        content = ''
        for c in el.contents:
            if c.name == 'p':
                content += c.renderContents()
            elif c.name != 'ul' and c.name != 'div':
                content += str(c).rstrip()

        return content

    def front(self):
        front = []
        if self.parent and self.content.startswith(': '):
            front += self.parent.front()
            front.append(self.content[2:])
        else:
            front.append(self.content)

        return front

    def back(self):
        back = []
        for child in self.children:
            if child.content.startswith(': '):
                back.append(child.content[2:])
            else:
                back.append(child.content)
        return back

    def hash(self):
        s = str(self.front() + self.back())
        return hashlib.md5(s).hexdigest()


################################################################################
# DOCUMENT
################################################################################

class Document:

    def __init__(self, path, hash, root_dir=ROOT_DIR):
        self.hash = hash
        self.path = path
        self.root_dir = root_dir
        self._registry = None
        self._root = None
        self._content_hash = None
        self.loaded = False

    def absolute_path(self):
        return '%s/%s' % (self.root_dir, self.path)

    def root(self):
        if not self.loaded:
            self.load()
        return self._root

    def content_hash(self):
        if not self.loaded:
            self.load()
        return self._content_hash

    def registry(self):
        if not self.loaded:
            self.load()
        return self._registry

    def _find_root(self, tree):
        root = tree.select('h1')
        if not root:
            uls = tree.select('ul')
            if uls:
                ul = uls[0]
                root = ul.select('> li')
        return root[0]


    def load(self, func=None):
        with codecs.open(self.absolute_path(), encoding='utf-8') as f:
            content = f.read()
            html = markdown.markdown(content, extensions=[CodeHiliteExtension(guess_lang=True)])
            tree = BeautifulSoup(html, 'lxml')
            root = self._find_root(tree)
            self._content_hash = (hashlib.md5(content).hexdigest())
            self._registry = {}
            self._root = Chunk(root, None, self._registry, func=func)
            self.loaded = True

################################################################################
# BANDIT
################################################################################

class Bandit:

    def __init__(self, document, data):
        self.document = document
        self.data = data

    def pull(self):
        best_arm = None
        highest_sample = -float('inf')

        eligible_arms = set(self.data['chunks'].keys()) - set(self.data['last_n'])
        if not eligible_arms:
            eligible_arms = set(self.data['chunks'].keys())

        for arm_hash in eligible_arms:
            arm_data = self.data['chunks'][arm_hash]
            sample = st.beta(1 + arm_data['misses'], 1 + arm_data['hits']).rvs()

            offset = max(0, HITS_TO_COMPLETE - arm_data['hits'])

            # offset = 0
            # if arm_data['hits'] > 1:
            if arm_data['hits'] >= HITS_TO_COMPLETE:
                last_hit = arm_data['last_hits'][-2]
                parsed = datetime.strptime(last_hit, DATE_FORMAT)
                now = datetime.now()
                diff = now - parsed
                offset -= offset * (2 ** -( (diff.seconds / 60.0) / PULL_HALF_LIFE) )
            #     # offset = (10 ** -( (diff.seconds / 60.0) / 5) )

            sample = sample + offset

            if sample > highest_sample:
                best_arm = arm_hash
                highest_sample = sample

        return self.document.registry()[best_arm]

    def reward(self, value, chunk_hash):
        arm_info = self.data['chunks'][chunk_hash]
        if not arm_info:
            return False

        if value == 0:
            self.data['chunks'][chunk_hash]['hits'] += 1
            last_hits = deque(self.data['chunks'][chunk_hash]['last_hits'], HITS_TO_COMPLETE)
            last_hits.append(datetime.now().strftime(DATE_FORMAT))
            self.data['chunks'][chunk_hash]['last_hits'] = list(last_hits)
        elif value == 1:
            self.data['chunks'][chunk_hash]['misses'] += 1
            self.data['chunks'][chunk_hash]['hits'] = 0
            self.data['chunks'][chunk_hash]['last_hits'] = []
        else:
            return False

        last_n = deque(self.data['last_n'], LAST_N)
        last_n.append(chunk_hash)
        self.data['last_n'] = list(last_n)

        return True

################################################################################
# BANDIT ENGINE
################################################################################

class BanditEngine:

    def __init__(self, data):
        self.data = data

    def fix_document_hashes(self, document):
        hash_exists = document.hash in self.data
        if hash_exists:
            self.data[document.hash]['content_hash'] = document.content_hash()
        else:
            data_copy = copy.deepcopy(self.data)
            for document_hash, data in data_copy.iteritems():
                if data['content_hash'] == document.content_hash():
                    data['path'] = document.path
                    self.data[document.hash] = data
                    del self.data[document_hash]
                    break

    def fix_chunks_hashes(self, document):
        active_chunks_hashes = set(document.registry().keys())
        current_bandit_hashes = set(self.data[document.hash]['chunks'].keys())
        obsolete_hashes = current_bandit_hashes - active_chunks_hashes
        new_hashes = active_chunks_hashes - current_bandit_hashes
        for h in obsolete_hashes:
            del self.data[document.hash]['chunks'][h]
        for h in new_hashes:
            self.data[document.hash]['chunks'][h] = {'misses': 0, 'hits': 0, 'last_hits': []}

    def _post_create_chunk(self, chunk, registry):
        if len(chunk.children) > 0:
            registry[chunk.hash()] = chunk


    def initialize_data(self, document):
        data = self.data.get(document.hash)
        if not data:
            self.data[document.hash] = {
                'content_hash': document.content_hash(),
                'path': document.path,
                'chunks': {},
                'last_n': [],
                'id': document.hash
            }

    def update(self, document):
        document.load(self._post_create_chunk)
        self.fix_document_hashes(document)
        self.initialize_data(document)
        self.fix_chunks_hashes(document)

    def load(self, document):
        data = self.data[document.hash]
        return Bandit(document, data)

    def completed(self, document):
        data = self.data.get(document.hash)

        if not data:
            return 0

        total_chunks = len(data['chunks'])
        residual = 0.0
        for chunk_hash, chunk in data['chunks'].iteritems():
            for hit in chunk['last_hits'][::-1][:HITS_TO_COMPLETE]:
                parsed = datetime.strptime(hit, DATE_FORMAT)
                now = datetime.now()
                diff = now - parsed
                residual += (2 ** -(diff.days / COMPLETION_HALF_LIFE))

        return int(round(residual / (HITS_TO_COMPLETE * total_chunks), 2) * 100)

################################################################################
# BANDIT REPOSITORYi
################################################################################

class BanditRepository:

    def __init__(self, chunktfile=CHUNKTFILE):
        self.chunktfile = chunktfile

    def load_engine_data(self):
        if not os.path.exists(self.chunktfile):
            return {}

        with codecs.open(self.chunktfile, 'r', encoding='utf-8') as chunktfile:
            data = {}
            for line in chunktfile:
                bandit = json.loads(line)
                data[bandit['id']] = bandit

            return data

    def save_engine_data(self, engine_data):
        with codecs.open(self.chunktfile, 'w', encoding='utf-8') as chunktfile:
            for bandit in engine_data:
                chunktfile.write(json.dumps(engine_data[bandit]) + '\n')

################################################################################
# DOCUMENT REPOSITORY
################################################################################

class DocumentRepository:

    def __init__(self, root_dir=ROOT_DIR):
        self.root_dir = root_dir

    def all(self):
        documents = []
        for root, dirs, files in os.walk(ROOT_DIR):
            for f in files:
                if f.endswith(".md"):
                    document_path = os.path.join(root.split('knods/')[1], f)
                    document_hash = hashlib.md5(document_path).hexdigest()
                    documents.append(Document(document_path, document_hash))

        return sorted(documents, key=lambda x: x.path)

    def find(self, document_hash):
        for document in self.all():
            if document.hash == document_hash:
                return document

################################################################################
# WEB SERVER
################################################################################

def load_bandit_engine(bandit_repository, document=None):
    engine_data = bandit_repository.load_engine_data()
    bandit_engine = BanditEngine(engine_data)
    if document:
        bandit_engine.update(document)

    return bandit_engine


@app.route('/')
def index():
    engine_data = BanditRepository(CHUNKTFILE).load_engine_data()
    bandit_engine = BanditEngine(engine_data)
    documents = DocumentRepository().all()
    return Template(INDEX_TEMPLATE).render(documents=documents, bandit_engine=bandit_engine)

@app.route('/<document_hash>/pull')
def pull(document_hash):
    document = DocumentRepository().find(document_hash)
    if not document:
        return 'Document not found', 404

    bandit_repository = BanditRepository(CHUNKTFILE)
    bandit_engine = load_bandit_engine(bandit_repository, document)
    bandit = bandit_engine.load(document)
    chunk = bandit.pull()
    bandit_repository.save_engine_data(bandit_engine.data)

    return Template(CHUNK_TEMPLATE).render(document=document, chunk=chunk, bandit_engine=bandit_engine)

@app.route('/<document_hash>/reward', methods=['POST'])
def reward(document_hash):
    document = DocumentRepository().find(document_hash)
    if not document:
        return 'Document not found', 404

    bandit_repository = BanditRepository(CHUNKTFILE)
    bandit_engine = load_bandit_engine(bandit_repository, document)
    bandit = bandit_engine.load(document)
    bandit.reward(int(request.form['value']), request.form['chunk_hash'])
    bandit_repository.save_engine_data(bandit_engine.data)

    return redirect(url_for('pull', document_hash=document_hash))

@app.before_request
def bootstrap():
    if not os.path.exists(ROOT_DIR):
        os.makedirs(ROOT_DIR)
    if not os.path.exists(CHUNKTFILE):
        with codecs.open(CHUNKTFILE, 'w', encoding='utf-8') as chunktfile:
            chunktfile.write('')


if __name__ == '__main__':
    app.run(debug=True)
