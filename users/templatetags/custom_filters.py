from django import template

register = template.Library()


@register.filter
def pl_number_format(value, decimals=2):
    """
    Formatuje liczbę wg polskiego stylu: spacja jako separator tysięcy,
    przecinek jako separator dziesiętny.
    Przykład: 1234567.89 -> "1 234 567,89"
    """
    try:
        value = float(value)
        formatted = f"{value:,.{decimals}f}"
        return formatted.replace(",", " ").replace(".", ",")
    except (ValueError, TypeError):
        return value
