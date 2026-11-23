# Third-party notices

The project MIT license applies to original TX-2 Replica code and documentation. The origins and terms below apply to materials from other sources.

## TX-2 Project simulator and assembler

The browser's Lincoln Writer character mapping in `web/lw.js` follows the upstream `base/src/charset.rs`. The browser tape library includes a repaired copy of the upstream `examples/hello.tape`. The assembler patch in `tools/sketchpad-assembler.patch` includes upstream code context. The upstream MIT notice is reproduced in full below. [Pinned TX-2 simulator source](https://github.com/TX-2/TX-2-simulator/tree/7480ac70bfece86c58b28a9f085ab4fe63880aae)

## Sketchpad and historical reference material

- Ivan Sutherland's Sketchpad program and the TX-2 Project transcription are separate historical sources. The pinned transcription has no license file. `make sketchpad` generates the reconstructed tape, memory image and change manifest. The browser package includes the reconstructed tape as `tapes/sketchpad.tape`. [Upstream reconstruction notes](https://github.com/TX-2/Sketchpad/blob/3d134b23d207f169d0fb65ac5768177867689ed2/RECONSTRUCTION.md#publication-gate)
- `tapes/inchworm.tape` is a paper-tape adaptation of H. Philip Peterson's 1958 Inchworm listing. See `programs/inchworm.words` for the adapted octal words and reconstruction notes. [Original listing, 6M-5780](https://bitsavers.org/pdf/mit/tx-2/6M-5780_Some_Examples_of_TX-2_Programming_Jul1958.pdf#page=7)
- Scans, crops and other reproductions, including extracted text and OCR in `references/`, retain their source-specific terms. The Computer History Museum's archive states that commercial use of its content requires written permission. For other archival items, consult the source record for each item. The MIT license covers the project's own analysis and tools for working with these materials. [Computer History Museum archive notice](https://github.com/computerhistory/Historical-Highlights-Documents-Repository#readme)
- The plugboard words in `rtl/tx2_memory.v` and the standard reader leader used by the example tapes reproduce historical TX-2 boot listings from the *TX-2 Users Handbook*. The reader leader comes from the upstream assembler's implementation. [Historical reader leader listing](https://archive.org/details/tx-2-users-handbook-nov-63/page/n150/mode/1up)

## Handwritten digits model

The DIGITS classifier was trained on the [MNIST handwritten digit database](https://huggingface.co/datasets/ylecun/mnist) by Yann LeCun, Corinna Cortes, and Christopher J. C. Burges, plus synthetic pen strokes. The repository and paper tape contain quantized model parameters, not the MNIST images.

## Compiled browser and native builds

The browser and native simulator link the Verilator runtime, which is dual-licensed under LGPL-3.0-only or Artistic-2.0. Browser builds also include Emscripten-generated JavaScript and code from the SDK's linked system libraries. When distributing compiled artifacts, retain the applicable license texts and notices for the runtime and libraries included by the actual toolchain. [Verilator licensing](https://verilator.org/guide/latest/copyright.html) · [Emscripten licensing](https://emscripten.org/docs/introducing_emscripten/emscripten_license.html)

## TX-2 Simulator Project MIT notice

```text
Copyright (c) 2021-2025 The TX-2 Simulator Project Developers

Permission is hereby granted, free of charge, to any
person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the
Software without restriction, including without
limitation the rights to use, copy, modify, merge,
publish, distribute, sublicense, and/or sell copies of
the Software, and to permit persons to whom the Software
is furnished to do so, subject to the following
conditions:

The above copyright notice and this permission notice
shall be included in all copies or substantial portions
of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF
ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED
TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT
SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR
IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.

// SPDX-License-Identifier: MIT
https://opensource.org/license/MIT
```
