"""briefing.pptx → briefing.pdf (LibreOffice UNO).

LibreOffice 는 한글과 영문·숫자 사이에 자동으로 간격을 넣어서('뉴욕증시 , AI') 이미지가 어색해진다.
모든 문단에서 그 옵션(ParaIsCharacterDistance)을 끄고 PDF 로 내보낸다. PowerPoint 에서 열 때는 영향 없음.
시스템 파이썬으로 실행: /usr/bin/python3 scripts/pptx2pdf.py briefing/briefing.pptx
"""
import subprocess
import sys
import time
from pathlib import Path

import uno
from com.sun.star.beans import PropertyValue


def pv(name, value):
    p = PropertyValue()
    p.Name, p.Value = name, value
    return p


def main(src):
    src = Path(src).resolve()
    office = subprocess.Popen(["soffice", "--headless", "--invisible", "--norestore",
                               "--accept=socket,host=127.0.0.1,port=2002;urp;"])
    try:
        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
        for _ in range(60):
            try:
                ctx = resolver.resolve("uno:socket,host=127.0.0.1,port=2002;urp;StarOffice.ComponentContext")
                break
            except Exception:
                time.sleep(0.5)
        else:
            raise SystemExit("LibreOffice 에 연결하지 못했어요")
        desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        doc = desktop.loadComponentFromURL(uno.systemPathToFileUrl(str(src)), "_blank", 0, (pv("Hidden", True),))
        pages = doc.getDrawPages()
        for i in range(pages.getCount()):
            page = pages.getByIndex(i)
            for j in range(page.getCount()):
                shape = page.getByIndex(j)
                if not shape.supportsService("com.sun.star.drawing.Text"):
                    continue
                paras = shape.getText().createEnumeration()
                while paras.hasMoreElements():
                    paras.nextElement().setPropertyValue("ParaIsCharacterDistance", False)
        doc.storeToURL(uno.systemPathToFileUrl(str(src.with_suffix(".pdf"))), (pv("FilterName", "impress_pdf_Export"),))
        doc.close(True)
    finally:
        office.terminate()


if __name__ == "__main__":
    main(sys.argv[1])
