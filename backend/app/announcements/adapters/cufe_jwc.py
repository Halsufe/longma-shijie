from .html_adapter import GenericHtmlAdapter


class CufeJwcAdapter(GenericHtmlAdapter):
    def __init__(self, base_url: str = "https://jwc.cufe.edu.cn/"):
        super().__init__("cufe_jwc", base_url)

