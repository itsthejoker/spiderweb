from spiderweb.constants import DEFAULT_ENCODING
from spiderweb.response import TemplateResponse
from spiderweb.tests.helpers import setup


def test_str_template_with_static_tag():
    # test that the static tag works
    template = """
    <html>
        <head>
            <title>{{ title }}</title>
            <link rel="stylesheet" href="{% static 'style.css' %}">
        </head>
        <body>
            <h1>{{ title }}</h1>
            <p>{{ content }}</p>
        </body>
    </html>
    """
    context = {"title": "Test", "content": "This is a test."}
    app, environ, start_response = setup(
        staticfiles_dirs=["spiderweb/tests/staticfiles"], static_url="blorp"
    )

    @app.route("/")
    def index(request):
        return TemplateResponse(request, template_string=template, context=context)

    rendered_template = (
        template.replace("{% static 'style.css' %}", "/blorp/style.css")
        .replace("{{ title }}", "Test")
        .replace("{{ content }}", "This is a test.")
    )

    assert app(environ, start_response) == [bytes(rendered_template, DEFAULT_ENCODING)]


def test_str_template_with_url_tag():
    # test that the url tag works
    template = """
    <html>
        <body>
            <a href="{% url 'target_route' %}">Link</a>
        </body>
    </html>
    """
    app, environ, start_response = setup()

    @app.route("/")
    def index(request):
        return TemplateResponse(request, template_string=template)

    @app.route("/target", name="target_route")
    def target(request):
        pass

    rendered_template = template.replace("{% url 'target_route' %}", "/target")

    assert app(environ, start_response) == [bytes(rendered_template, DEFAULT_ENCODING)]
