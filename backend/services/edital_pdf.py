"""Bounded PDF-only ingestion. Original bytes stay in the request/child pipe.

Only the versioned extracted representation is durable input. No provider/key
is needed here. Geometry/heading/column/header labels are extraction hints.
"""
import asyncio
from collections import Counter
from dataclasses import dataclass
import hashlib
import io
from importlib.metadata import version
import json
import logging
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from statistics import median
from uuid import uuid4
from edital_pipeline_contracts import DocumentIR, SourcePage, SourceBlock, MAX_PAGES, MAX_BLOCKS, MAX_TEXT

MAX_BYTES = 20*1024*1024
MAX_RESULT = 12*1024*1024
EXTRACTION_SECONDS = 60
CHILD_CPU_SECONDS = 55
CHILD_ADDRESS_SPACE_BYTES = 384*1024*1024
logger = logging.getLogger(__name__)
_slots = asyncio.Semaphore(1)
_running = set()


class PDFInputError(Exception):
    def __init__(self,code,diagnostic=None,*,metrics=None):
        self.code=code
        self.diagnostic=diagnostic
        self.metrics=metrics
        super().__init__(code)


@dataclass(frozen=True)
class ExtractionMetrics:
    """Supervisor facts only; never child diagnostics, document text or paths."""
    reference: str
    duration_ms: int
    returncode: int | None
    stdout_bytes: int
    stdout_complete: bool
    cgroup_memory_before_bytes: int | None = None
    cgroup_memory_after_bytes: int | None = None
    cgroup_memory_peak_bytes: int | None = None
    cgroup_memory_max_bytes: int | None = None
    cgroup_oom_kill_delta: int | None = None

    @property
    def signal(self):
        return -self.returncode if os.name=='posix' and self.returncode is not None and self.returncode<0 else None

    def log(self,outcome,*,success=False):
        # outcome is a supervisor-owned literal, never a child-provided code.
        # RLIMIT_AS bounds virtual address space, not measured resident memory.
        log=logger.info if success else logger.warning
        log('edital_extraction outcome=%s reference=%s duration_ms=%d returncode=%s signal=%s '
            'stdout_bytes=%d stdout_complete=%s stdout_limit_exceeded=%s address_space_limit_bytes=%s '
            'cgroup_memory_before_bytes=%s cgroup_memory_after_bytes=%s cgroup_memory_peak_bytes=%s '
            'cgroup_memory_max_bytes=%s cgroup_oom_kill_delta=%s',
            outcome,self.reference,self.duration_ms,self.returncode,self.signal,
            self.stdout_bytes,self.stdout_complete,self.stdout_bytes>MAX_RESULT,
            CHILD_ADDRESS_SPACE_BYTES if sys.platform.startswith('linux') else None,
            self.cgroup_memory_before_bytes,self.cgroup_memory_after_bytes,self.cgroup_memory_peak_bytes,
            self.cgroup_memory_max_bytes,self.cgroup_oom_kill_delta)


def _cgroup_memory():
    """Best-effort v2 counters, never paths/text in logs or changes to limits.

    Peak is cgroup-lifetime high water, and OOM events concern the whole group;
    neither proves that this request caused an OOM. Missing/unlimited is None.
    """
    empty=(None,None,None,None)
    if not sys.platform.startswith('linux'):return empty
    def read(path,limit=256):
        try:
            with path.open(encoding='ascii') as source:return source.read(limit)
        except (OSError,UnicodeError):return ''
    def counter(value):
        value=value.strip()
        return int(value) if value.isascii() and value.isdigit() and len(value)<=20 else None
    root=Path('/sys/fs/cgroup');locations=[root]
    for line in read(Path('/proc/self/cgroup'),4096).splitlines():
        if line.startswith('0::/'):
            relative=Path(line[4:])
            if not relative.is_absolute() and '..' not in relative.parts:locations.append(root/relative)
    for directory in locations:
        current=counter(read(directory/'memory.current'))
        if current is None:continue
        peak=counter(read(directory/'memory.peak'))
        maximum=counter(read(directory/'memory.max'))
        events=dict(line.split() for line in read(directory/'memory.events',1024).splitlines() if len(line.split())==2)
        return current,peak,maximum,counter(events.get('oom_kill',''))
    return empty


def text_key(value):
    return ' '.join(value.split()).casefold()


def bbox(values):
    result=tuple(round(float(v),2) for v in values)
    if len(result)!=4 or not all(math.isfinite(v) for v in result) or result[0]>result[2] or result[1]>result[3]:
        raise PDFInputError('invalid_geometry')
    return result


def contains(box,word):
    x=(word['x0']+word['x1'])/2;y=(word['top']+word['bottom'])/2
    return box[0]<=x<=box[2] and box[1]<=y<=box[3]


def lines(words):
    """Geometric lines inside one column, without merging adjacent columns."""
    result=[]
    for word in sorted(words,key=lambda w:(w['top'],w['x0'])):
        if not result or abs(result[-1][0]['top']-word['top'])>3:
            result.append([word])
        else:result[-1].append(word)
    return [sorted(line,key=lambda w:w['x0']) for line in result]


def split_text(text,limit=2000):
    # Preserve every character, including an unusually long unbroken token.
    while text:
        end=len(text) if len(text)<=limit else text.rfind(' ',0,limit+1)
        if end<=0:end=min(limit,len(text))
        yield text[:end]
        text=text[end:].lstrip(' ')


def ordered(blocks,columns):
    if columns==1:return sorted(blocks,key=lambda b:(b['bbox'][1],b['bbox'][0]))
    # Full-width rows/headings divide reading bands. Read left then right within
    # a band; never flatten two columns into a single interleaved line.
    pivots=sorted({b['bbox'][1] for b in blocks if b['column']==0})
    import bisect
    return sorted(blocks,key=lambda b:(bisect.bisect_right(pivots,b['bbox'][1]),b['column'],b['bbox'][1],b['bbox'][0]))


def annotate_paragraphs(pages):
    """Hints retain source links; they never establish semantic applicability."""
    heading=None
    for page in pages:
        previous=None;paragraph=0
        for block in page.blocks:
            numbering=re.match(r'^(\d+(?:\.\d+){0,8})[.)]?(?:\s|$)',block.text)
            block.numbering_hint=numbering.group(1) if numbering else None
            if (previous is None or block.kind!='line' or previous.kind!='line' or block.column!=previous.column
                or numbering or block.bbox[1]-previous.bbox[3]>max(6,(block.bbox[3]-block.bbox[1])*.8)):
                paragraph+=1
            block.paragraph_hint=f'p{page.page:04d}-paragraph{paragraph:04d}'
            if not block.recurring_margin:
                block.parent_heading_hint=heading
                if block.kind=='heading_hint':heading=block.id
                previous=block


def extract_local(content):
    # Fail closed on stale deployments before parsing any untrusted CMap.
    miner_version=version('pdfminer.six')
    if not re.fullmatch(r'\d{8}',miner_version) or miner_version<'20251230':
        raise PDFInputError('parser_security_upgrade_required')
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError
    from pdfplumber import open as open_pdf
    from pdfminer.pdfparser import PDFSyntaxError
    from pdfminer.psparser import PSSyntaxError
    logging.disable(logging.CRITICAL)
    if not content.startswith(b'%PDF-'):raise PDFInputError('invalid_pdf')
    if not content or len(content)>MAX_BYTES:raise PDFInputError('file_size_limit')
    try:
        reader=PdfReader(io.BytesIO(content),strict=False)
        if reader.is_encrypted:raise PDFInputError('encrypted_pdf')
        count=len(reader.pages)
        if count<1:raise PDFInputError('no_pages')
        if count>MAX_PAGES:raise PDFInputError('page_limit')
        del reader
        pages=[];characters=0;block_count=0
        with open_pdf(io.BytesIO(content)) as pdf:
            for number,page in enumerate(pdf.pages,1):
                if not all(math.isfinite(float(n)) and 0<float(n)<=20000 for n in (page.width,page.height)):
                    raise PDFInputError('page_dimensions_limit')
                if len(page.chars)+len(page.lines)+len(page.rects)+len(page.curves)>50000 or len(page.images)>1000:
                    raise PDFInputError('page_complexity_limit')
                words=page.extract_words(x_tolerance=2,y_tolerance=3,extra_attrs=['size'])
                typical=median(float(w['size']) for w in words) if words else 12
                plain=' '.join(w['text'] for w in words)
                characters+=len(plain)
                if characters>MAX_TEXT:raise PDFInputError('text_limit')
                image_area=max((max(0,i['x1']-i['x0'])*max(0,i['bottom']-i['top']) for i in page.images),default=0)
                image_text_gap=any(max(0,i['x1']-i['x0'])*max(0,i['bottom']-i['top'])>page.width*page.height*.3
                    and sum(len(w['text']) for w in words if contains((i['x0'],i['top'],i['x1'],i['bottom']),w))<50 for i in page.images)
                if not plain.strip() and not (page.images or page.chars or page.curves or page.lines or page.rects):quality='blank'
                elif image_text_gap:quality='requires_ocr'
                elif len(plain.strip())<50 and (image_area>page.width*page.height*.3 or not words):quality='requires_ocr'
                elif plain.count('\ufffd')/max(len(plain),1)>.05:quality='requires_ocr'
                elif len(plain.strip())<50:quality='low_text'
                else:quality='text'
                middle=page.width/2
                left=[w for w in words if w['x1']<middle-12]
                right=[w for w in words if w['x0']>middle+12]
                crossing=[w for w in words if w['x0']<middle<w['x1']]
                overlap=min(max((w['bottom'] for w in left),default=0),max((w['bottom'] for w in right),default=0))-max(min((w['top'] for w in left),default=page.height),min((w['top'] for w in right),default=page.height))
                columns=2 if min(len(left),len(right))>=max(12,len(words)*.2) and len(crossing)<len(words)*.05 and overlap>page.height*.25 else 1
                blocks=[];table_words=set()
                for ti,table in enumerate(page.find_tables()):
                    matrix=table.extract(x_tolerance=2,y_tolerance=3)
                    header_hint=[str(c or '') for c in (matrix[0] if matrix else [])][:40]
                    if len(matrix)>2000:raise PDFInputError('table_limit')
                    for ri,(row,cells) in enumerate(zip(table.rows,matrix)):
                        if len(cells)>40:raise PDFInputError('table_limit')
                        values=[str(c or '') for c in cells]
                        text=' | '.join(values).strip(' |')
                        if not text:continue
                        row_box=bbox(row.bbox)
                        for wi,word in enumerate(words):
                            for cell_box,cell_text in zip(row.cells,values):
                                if cell_box and contains(cell_box,word) and text_key(word['text']) in text_key(cell_text):
                                    table_words.add(wi);break
                        table_id=f'p{number:04d}-table{ti+1:03d}'
                        column=0 if columns==1 or row_box[0]<middle<row_box[2] else 1 if row_box[2]<=middle else 2
                        for part_index,part in enumerate(split_text(text)):
                            blocks.append({'text':part,'bbox':row_box,'kind':'table_row','column':column,
                                'table_id':table_id,'table_header_hint':header_hint,'cells':values,
                                'continuation_of':f'{table_id}-row{ri+1}' if part_index else None})
                remaining=[w for wi,w in enumerate(words) if wi not in table_words]
                groups={0:remaining} if columns==1 else {0:[w for w in remaining if w['x0']<middle<w['x1']],
                    1:[w for w in remaining if w['x1']<=middle],2:[w for w in remaining if w['x0']>=middle]}
                for column,group in groups.items():
                    for line in lines(group):
                        text=' '.join(w['text'] for w in line)
                        box=bbox((min(w['x0'] for w in line),min(w['top'] for w in line),max(w['x1'] for w in line),max(w['bottom'] for w in line)))
                        heading=len(text)<200 and (max(float(w['size']) for w in line)>=typical*1.15 or text.isupper())
                        for part_index,part in enumerate(split_text(text)):
                            blocks.append({'text':part,'bbox':box,'kind':'heading_hint' if heading else 'line','column':column,
                                'continuation_of':f'p{number:04d}-line-{column}-{box[1]}' if part_index else None})
                blocks=[SourceBlock(id=f'p{number:04d}-b{index:04d}',page=number,**block) for index,block in enumerate(ordered(blocks,columns),1)]
                block_count+=len(blocks)
                if block_count>MAX_BLOCKS or len(blocks)>2000:raise PDFInputError('block_limit')
                pages.append(SourcePage(page=number,width=page.width,height=page.height,quality=quality,
                    characters=len(plain),column_hint=columns,image_count=len(page.images),blocks=blocks))
                page.close()
        if len(pages)!=count:raise PDFInputError('page_coverage')
        margin_counts=Counter()
        for page in pages:
            margin_counts.update({text_key(b.text) for b in page.blocks if b.bbox[1]<page.height*.08 or b.bbox[3]>page.height*.92})
        for page in pages:
            for block in page.blocks:
                if (block.bbox[1]<page.height*.08 or block.bbox[3]>page.height*.92) and margin_counts[text_key(block.text)]>=max(3,math.ceil(count*.4)):
                    block.recurring_margin=True
        annotate_paragraphs(pages)
        warnings=[]
        if any(p.quality=='requires_ocr' for p in pages):warnings.append('requires_selective_ocr_unavailable')
        if any(p.quality=='low_text' for p in pages):warnings.append('low_text_pages_require_review')
        if any(p.column_hint==2 for p in pages):warnings.append('column_order_is_a_layout_hint')
        return DocumentIR(sha256=hashlib.sha256(content).hexdigest(),size_bytes=len(content),pages=pages,warnings=warnings)
    except PDFInputError:raise
    except MemoryError:raise PDFInputError('memory_limit') from None
    except (PdfReadError,PDFSyntaxError,PSSyntaxError) as error:raise PDFInputError('unreadable_pdf',type(error).__name__) from None
    except Exception as error:raise PDFInputError('parser_internal_error',type(error).__name__) from None


def child_limits():
    # Production Linux enforces process CPU/address-space bounds. Windows has
    # the same input/page/output/deadline bounds, but no claimed RLIMIT support.
    try:import resource
    except ImportError:return
    resource.setrlimit(resource.RLIMIT_CPU,(CHILD_CPU_SECONDS,CHILD_CPU_SECONDS))
    resource.setrlimit(resource.RLIMIT_AS,(CHILD_ADDRESS_SPACE_BYTES,CHILD_ADDRESS_SPACE_BYTES))
    resource.setrlimit(resource.RLIMIT_FSIZE,(0,0))


def supervised(content):
    if len(content)>MAX_BYTES:raise PDFInputError('file_size_limit')
    # Do not pass database/provider credentials to an untrusted-document parser.
    env={key:value for key,value in os.environ.items() if key.upper() in ('PATH','SYSTEMROOT','WINDIR','TEMP','TMP','LANG','LC_ALL')}
    env.update(PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1')
    reference=uuid4().hex[:12]
    memory_before=_cgroup_memory()
    started=time.monotonic()
    def measured(returncode,stdout,complete=True):
        memory_after=_cgroup_memory()
        before_kills,after_kills=memory_before[3],memory_after[3]
        delta=after_kills-before_kills if before_kills is not None and after_kills is not None and after_kills>=before_kills else None
        return ExtractionMetrics(reference,max(0,round((time.monotonic()-started)*1000)),
            returncode,len(stdout),complete,memory_before[0],memory_after[0],memory_after[1],memory_after[2],delta)
    try:
        result=subprocess.run([sys.executable,'-m','services.edital_pdf'],input=content,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
            timeout=EXTRACTION_SECONDS,cwd=Path(__file__).resolve().parents[1],env=env,check=False)
    except subprocess.TimeoutExpired as error:
        # run() reaps the killed child but does not expose its returncode.
        # Partial stdout is a lower bound; do not invent a signal/OOM cause.
        metrics=measured(None,error.stdout or b'',False)
        metrics.log('timeout')
        raise PDFInputError('extraction_timeout',metrics=metrics) from None
    except OSError:
        metrics=measured(None,b'',False)
        metrics.log('launch_failed')
        raise PDFInputError('extraction_process_failed',metrics=metrics) from None
    metrics=measured(result.returncode,result.stdout)
    if result.returncode!=0:
        metrics.log('process_failed')
        raise PDFInputError('extraction_process_failed',metrics=metrics)
    if len(result.stdout)>MAX_RESULT:
        metrics.log('result_limit')
        raise PDFInputError('extraction_result_limit',metrics=metrics)
    try:
        payload=json.loads(result.stdout)
        if not isinstance(payload,dict):raise ValueError('Invalid protocol')
        if not payload.get('ok'):
            metrics.log('child_rejected')
            code=payload.get('code')
            raise PDFInputError(code if isinstance(code,str) else 'extraction_failed',payload.get('diagnostic'),metrics=metrics)
        document=DocumentIR.model_validate(payload['document'])
    except (ValueError,UnicodeError,KeyError,TypeError):
        metrics.log('invalid_result')
        raise PDFInputError('extraction_failed',metrics=metrics) from None
    metrics.log('completed',success=True)
    return document


async def extract_pdf(content):
    # A second concurrent HTTP request gets a bounded wait rather than starting
    # another expensive parser in this web process. Durable admission is separate.
    admission=_slots
    try:await asyncio.wait_for(admission.acquire(),timeout=1)
    except asyncio.TimeoutError:raise PDFInputError('ingestion_busy') from None
    task=asyncio.create_task(asyncio.to_thread(supervised,content))
    _running.add(task)
    def finished(worker):
        _running.discard(worker);admission.release()
        if not worker.cancelled():worker.exception()  # Drain failures after an HTTP disconnect.
    task.add_done_callback(finished)
    # Cancelling HTTP must not release admission while its child still parses.
    return await asyncio.shield(task)


if __name__=='__main__':
    child_limits()
    try:
        document=extract_local(sys.stdin.buffer.read(MAX_BYTES+1))
        payload=json.dumps({'ok':True,'document':document.model_dump(mode='json')},ensure_ascii=False).encode('utf-8')
        if len(payload)>MAX_RESULT:raise PDFInputError('extraction_result_limit')
    except PDFInputError as error:payload=json.dumps({'ok':False,'code':error.code,'diagnostic':error.diagnostic}).encode('utf-8')
    except Exception:payload=b'{"ok":false,"code":"extraction_failed"}'
    sys.stdout.buffer.write(payload)
