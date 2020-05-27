# Copyright 2017 Mycroft AI, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import re
import sys

from mycroft.util import LOG
from mycroft.version import check_version

import ddg3 as ddg

from mycroft.skills.common_query_skill import CommonQuerySkill, CQSMatchLevel
from mycroft.configuration import Configuration
from os.path import dirname, join, realpath
import json
from mtranslate import translate


def split_sentences(text):
    """
    Turns a string of multiple sentences into a list of separate ones
    handling the edge case of names with initials
    As a side effect, .?! at the end of a sentence are removed
    """
    text = re.sub(r' ([^ .])\.', r' \1~.~', text)
    text = text.replace('Inc.', 'Inc~.~')
    for c in '!?':
        text = text.replace(c + ' ', '. ')
    sents = text.split('. ')
    sents = [i.replace('~.~', '.') for i in sents]
    if sents[-1][-1] in '.!?':
        sents[-1] = sents[-1][:-1]
    print(sents)
    return sents


class DuckduckgoSkill(CommonQuerySkill):
    config = Configuration.get()
    # Set the active lang to match the configured one
    lang=(config.get('lang', 'en-us'))

    # Confirmations vocabs
    with open((dirname(realpath(__file__))+"/locale/"+lang+"/text.json"),encoding='utf8') as f:
        texts = json.load(f)
    
    
    # Only ones that make sense in
    # <question_word> <question_verb> <noun>
    question_words = texts.get('question_words')
    # Note the spaces
    question_verbs = texts.get('question_verbs')
    articles = texts.get('articles')
    start_words = texts.get('start_words')
    is_verb = texts.get('is_verb')
    in_word = texts.get('in_word')

    def __init__(self):
        super(DuckduckgoSkill, self).__init__()
        self.autotranslate = self.settings.get('autotranslate', True)
        self.log.debug("autotranslate: {}".format(self.autotranslate))
        config = Configuration.get()
        self.lang = config.get('lang', 'en-us')

    @classmethod
    def format_related(cls, abstract, query):
        LOG.debug('Original abstract: ' + abstract)
        ans = abstract

        if ans[-2:] == '..':
            while ans[-1] == '.':
                ans = ans[:-1]

            phrases = ans.split(', ')
            first = ', '.join(phrases[:-1])
            last = phrases[-1]
            if last.split()[0] in cls.start_words:
                ans = first
            last_word = ans.split(' ')[-1]
            while last_word in cls.start_words or last_word[-3:] == 'ing':
                ans = ans.replace(' ' + last_word, '')
                last_word = ans.split(' ')[-1]

        category = None
        match = re.search(r'\(([a-z ]+)\)', ans)
        if match:
            start, end = match.span(1)
            if start <= len(query) * 2:
                category = match.group(1)
                ans = ans.replace('(' + category + ')', '()')

        words = ans.split()
        for article in cls.articles:
            article = article.title()
            if article in words:
                index = words.index(article)
                if index <= 2 * len(query.split()):
                    name, desc = words[:index], words[index:]
                    desc[0] = desc[0].lower()
                    ans = ' '.join(name) + cls.is_verb + ' '.join(desc)
                    break

        if category:
            ans = ans.replace('()', cls.in_word + category)

        if ans[-1] not in '.?!':
            ans += '.'
        return ans

    def respond(self, query):
        if len(query) == 0:
            return 0.0

        if self.autotranslate and self.lang[:2] != 'en':
            query_tr = translate(query, from_language=self.lang[:2], 
                            to_language='en')
            self.log.debug("translation: {}".format(query_tr))

        r = ddg.query(query_tr)

        LOG.debug('Query: ' + str(query))
        LOG.debug('Query_tr: ' + str(query_tr))
        LOG.debug('Type: ' + r.type)

        if (r.answer is not None and r.answer.text and
                "HASH" not in r.answer.text):
            LOG.debug('Answer: ' + str(r.answer.text))
            if self.autotranslate and self.lang[:2] != 'en':
                    response = translate(r.answer.text, from_language='en', 
                                         to_language=self.lang[:2])
            else:
                response = r.answer.text
            return(query + self.is_verb + response + '.')

        elif len(r.abstract.text) > 0:
            LOG.debug('Abstract: ' + str(r.abstract.text))
            sents = split_sentences(r.abstract.text)
            if self.autotranslate and self.lang[:2] != 'en':
                for sent in sents:
                    sent = translate(sent, from_language='en', 
                                         to_language=self.lang[:2])
            return sents[0]

        elif len(r.related) > 0 and len(r.related[0].text) > 0:
            related = split_sentences(r.related[0].text)[0]
            answer = self.format_related(related, query)
            LOG.debug('Related: ' + str(answer))
            if self.autotranslate and self.lang[:2] != 'en':
                    answer= translate(answer, from_language='en', 
                                         to_language=self.lang[:2])
            return(answer)
        else:
            return None

    def CQS_match_query_phrase(self, query):
        answer = None
        for noun in self.question_words:
            for verb in self.question_verbs:
                for article in [i + ' ' for i in self.articles] + ['']:
                    test = noun + verb + ' ' + article
                    if query[:len(test)] == test:
                        answer = self.respond(query[len(test):])
                        break
        if answer:
            return (query, CQSMatchLevel.CATEGORY, answer)
        else:
            return None

    def stop(self):
        pass


def create_skill():
    return DuckduckgoSkill()
