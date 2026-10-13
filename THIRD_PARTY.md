# Third-party code

`harness/market.py` and `harness/prompts.py` are re-implementations of, and `harness/prompts.py`
contains text copied verbatim from, **algorithmic_pricing_llms** by Moritz Peist, Julian Romero
and Lucia Sauer (https://github.com/luciasauer/algorithmic_pricing_llms, commit 1138244), which is
licensed under the MIT License:

    MIT License

    Copyright (c) 2025 Moritz Peist, Julian Romero & Lucia Sauer

    Permission is hereby granted, free of charge, to any person obtaining a copy of this software
    and associated documentation files (the "Software"), to deal in the Software without
    restriction, including without limitation the rights to use, copy, modify, merge, publish,
    distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the
    Software is furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all copies or
    substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
    BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
    NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
    DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

That repository in turn follows the experimental design of Fish, Gonczarowski & Shorrer,
"Algorithmic Collusion by Large Language Models" (arXiv:2404.00806), and the demand model of
Calvano, Calzolari, Denicolò & Pastorello (AER 2020).

Deliberate differences from the source repo: the logit demand is re-derived for the single-group
case (verified numerically identical); `memory_length = 0` means "no market history" (the source
returns the whole history because of `list[-0:]`); and the JSON schema line sent to the model has
commas between fields.
