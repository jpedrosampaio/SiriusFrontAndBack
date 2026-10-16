"""Small synthetic PDFs, never user documents or board-specific templates."""
import io
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject,NameObject,NumberObject,DecodedStreamObject


def text(x,y,value,size=12):
    escaped=value.replace('\\','\\\\').replace('(','\\(').replace(')','\\)')
    return f'BT /F1 {size} Tf {x} {y} Td ({escaped}) Tj ET'


def pdf(pages,password=None):
    writer=PdfWriter()
    for commands in pages:
        page=writer.add_blank_page(width=600,height=800)
        font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),
            NameObject('/BaseFont'):NameObject('/Helvetica'),NameObject('/Encoding'):NameObject('/WinAnsiEncoding')})
        resources=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
        if commands is None:
            image=DecodedStreamObject();image.set_data(b'\xff\xff\xff')
            image.update({NameObject('/Type'):NameObject('/XObject'),NameObject('/Subtype'):NameObject('/Image'),
                NameObject('/Width'):NumberObject(1),NameObject('/Height'):NumberObject(1),
                NameObject('/ColorSpace'):NameObject('/DeviceRGB'),NameObject('/BitsPerComponent'):NumberObject(8)})
            resources[NameObject('/XObject')]=DictionaryObject({NameObject('/Im1'):writer._add_object(image)})
            commands=['q 500 0 0 650 40 40 cm /Im1 Do Q']
        page[NameObject('/Resources')]=resources
        stream=DecodedStreamObject();stream.set_data('\n'.join(commands).encode('cp1252'))
        page[NameObject('/Contents')]=writer._add_object(stream)
    if password:writer.encrypt(password)
    output=io.BytesIO();writer.write(output);return output.getvalue()


def columns():
    return pdf([[text(50,750,'Programa das provas',16),
        *[text(x,710-n*24,f'{label} {n+1} Tema original preservado') for x,label in [(50,'Esquerda'),(330,'Direita')] for n in range(12)]]])


def table():
    commands=[text(50,750,'Quadro de cargos e vagas',16)]
    for x in (50,300,550):commands.append(f'{x} 500 m {x} 650 l S')
    for y in (500,550,600,650):commands.append(f'50 {y} m 550 {y} l S')
    for y,left,right in [(620,'Perfil profissional','Vagas previstas'),(570,'Analista de Sistemas','Cadastro de reserva'),(520,'Especialista financeiro','12 vagas')]:
        commands.extend([text(65,y,left),text(315,y,right)])
    return pdf([commands])
