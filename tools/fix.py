import copy
from core.models.article import Article
def fix_html(content:str):
    if not content:
        return ""
    from core.content_format import format_content
    from tools.mdtools.md2html import convert_markdown_to_html
    from tools.htmltools import htmltools
    
    content = htmltools.clean_html(content,remove_attributes= [{'src': ''}],
                         remove_ids=['content_bottom_interaction','activity-name','meta_content',"js_article_bottom_bar","js_pc_weapp_code","js_novel_card","js_pc_qr_code"]
                         )
    if not content:
        return ""
    content=format_content(content,content_format='markdown')
    if not content:
        return ""
    content=convert_markdown_to_html(content)
    return content
def fix_article(article):
    art=article.to_dict()
    art['content']=fix_html(art.get('content') or "")
    return art
