from .html_adapter import GenericHtmlAdapter


class CufeMseAdapter(GenericHtmlAdapter):
    def __init__(self, base_url: str = "https://mse.cufe.edu.cn/"):
        super().__init__("cufe_mse", base_url)

