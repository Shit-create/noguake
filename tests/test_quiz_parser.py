"""Tests for quiz_parser core logic."""
from __future__ import annotations

import pytest

from src.quiz_parser import (
    Question,
    _choose_count,
    _infer_answers,
    _is_dismissed,
    _match_score,
    _normalize,
    _split_stem_options,
    parse_text,
)


class TestNormalize:
    def test_lowercase(self):
        assert _normalize("Hello World") == "hello world"

    def test_collapse_whitespace(self):
        assert _normalize("a   b\n\tc") == "a b c"

    def test_strip(self):
        assert _normalize("  text  ") == "text"


class TestChooseCount:
    def test_default_single(self):
        assert _choose_count("What is X?") == 1

    def test_choose_two(self):
        assert _choose_count("(Choose two)") == 2

    def test_choose_three(self):
        assert _choose_count("(Choose three)") == 3

    def test_choose_four(self):
        assert _choose_count("(Choose four)") == 4

    def test_choose_digit(self):
        assert _choose_count("(Choose 3)") == 3

    def test_case_insensitive(self):
        assert _choose_count("(CHOOSE TWO)") == 2


class TestMatchScore:
    def test_exact_match(self):
        score = _match_score("It provides high bandwidth", "It provides high bandwidth for users")
        assert score > 100

    def test_no_match(self):
        score = _match_score("Some option text", "completely unrelated explanation")
        assert score == 0.0

    def test_short_option(self):
        score = _match_score("ab", "ab appears in explanation")
        assert score == 0.0

    def test_core_match_after_stop_words(self):
        score = _match_score(
            "the network administrator configures",
            "the network administrator configures the device properly",
        )
        assert score > 50


class TestIsDismissed:
    def test_dismissed_by_incorrect(self):
        assert _is_dismissed("using static routing", "using static routing is incorrect")

    def test_dismissed_by_will_not(self):
        assert _is_dismissed(
            "using static routes",
            "using static routes will not work in this scenario",
        )

    def test_not_dismissed(self):
        assert not _is_dismissed("Option A contents", "Option A contents is correct")


class TestSplitStemOptions:
    def test_question_mark_split(self):
        stem, opts = _split_stem_options(
            "What is the capital of France?\n"
            "Paris\n"
            "London\n"
            "Berlin\n"
            "Madrid\n"
        )
        assert "What is the capital of France?" == stem
        assert len(opts) == 4

    def test_choose_two_in_stem(self):
        stem, opts = _split_stem_options(
            "Which protocols are used? (Choose two)\n"
            "TCP\n"
            "UDP\n"
            "HTTP\n"
        )
        assert "choose two" in stem.lower()
        assert len(opts) == 3

    def test_option_continuation(self):
        stem, opts = _split_stem_options(
            "What is true?\n"
            "a long option that spans\n"
            "multiple lines in the text\n"
            "another option\n"
        )
        assert len(opts) == 2
        assert "multiple lines" in opts[0]

    def test_permitted_or_denied_split(self):
        stem, opts = _split_stem_options(
            "Which type of traffic is permitted or denied?\n"
            "permitted\n"
        )
        assert opts == ["permitted", "denied"]

    def test_noise_line_truncation(self):
        stem, opts = _split_stem_options(
            "What is routing?\n"
            "A process\n"
            "Related Posts\n"
            "extra noise\n"
        )
        assert len(opts) == 1
        assert opts[0] == "A process"


class TestInferAnswers:
    def test_single_answer_strong_match(self):
        explanation = "The correct answer is Paris because it is the capital of France."
        opts = ["Paris", "London", "Berlin"]
        answers = _infer_answers(opts, explanation, "What is the capital?")
        assert answers == ["Paris"]

    def test_multi_answer(self):
        explanation = "TCP and UDP are both transport layer protocols."
        opts = ["TCP", "UDP", "HTTP"]
        answers = _infer_answers(opts, explanation, "Which protocols? (Choose two)")
        assert len(answers) == 2
        assert "TCP" in answers
        assert "UDP" in answers


CCNA_SAMPLE = """
1. What is the primary purpose of a router?

the router forwards packets between networks
the router stores data packets
the router manages DNS records

Explanation:
A router's primary purpose is to forward packets between networks based on routing table entries.

2. Which two protocols operate at the transport layer? (Choose two)

TCP
UDP
HTTP
FTP
ICMP

Explanation:
TCP and UDP are transport layer protocols. HTTP and FTP operate at the application layer. ICMP operates at the network layer."""


class TestParseText:
    def test_parse_ccna_sample(self):
        qs = parse_text(CCNA_SAMPLE, source="test.txt")
        assert len(qs) == 2

        q1 = qs[0]
        assert q1.number == 1
        assert "router" in q1.stem.lower()
        assert "router forwards packets" in q1.options[0]
        assert q1.qtype == "single"

        q2 = qs[1]
        assert q2.number == 2
        assert q2.qtype == "multi"
        assert "TCP" in q2.options
        assert "UDP" in q2.options

    def test_empty_text(self):
        assert parse_text("", source="test.txt") == []


class TestQuestionDataclass:
    def test_search_text(self):
        q = Question(
            number=1,
            stem="What is X?",
            options=["Answer A", "Answer B"],
            answer=["Answer A"],
            qtype="single",
            source="test.pdf",
        )
        st = q.search_text
        assert "what is x" in st
        assert "answer a" in st
        assert "answer b" in st
