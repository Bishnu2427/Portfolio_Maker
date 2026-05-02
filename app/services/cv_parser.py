import os


class CVParser:
    @staticmethod
    def parse(file_path: str) -> str:
        if not file_path or not os.path.exists(file_path):
            return ''
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.pdf':
            return CVParser._parse_pdf(file_path)
        if ext in ('.docx', '.doc'):
            return CVParser._parse_docx(file_path)
        if ext == '.txt':
            return CVParser._parse_txt(file_path)
        return ''

    @staticmethod
    def _parse_pdf(path: str) -> str:
        try:
            import PyPDF2
            text = ''
            with open(path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text += extracted + '\n'
            return text.strip()
        except Exception as e:
            print(f'[CVParser] PDF error: {e}')
            return ''

    @staticmethod
    def _parse_docx(path: str) -> str:
        try:
            import docx
            doc = docx.Document(path)
            return '\n'.join(p.text for p in doc.paragraphs if p.text).strip()
        except Exception as e:
            print(f'[CVParser] DOCX error: {e}')
            return ''

    @staticmethod
    def _parse_txt(path: str) -> str:
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read().strip()
        except Exception as e:
            print(f'[CVParser] TXT error: {e}')
            return ''
