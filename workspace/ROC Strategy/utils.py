from AlgorithmImports import *

def get_market_cap_thresholds():
    """
    Returns a dictionary mapping market cap tiers to their respective thresholds in USD.
    """
    return {
        'micro': (0, 300e6),
        'small': (300e6, 2e9),
        'mid': (2e9, 10e9),
        'large': (10e9, 200e9),
        'mega': (200e9, float('inf'))
    }

def get_sector_name_to_code():
    """
    Returns a dictionary mapping sector names to MorningstarSectorCode enums.
    """
    return {
        'basic materials': MorningstarSectorCode.BASIC_MATERIALS,
        'communication services': MorningstarSectorCode.COMMUNICATION_SERVICES,
        'consumer cyclical': MorningstarSectorCode.CONSUMER_CYCLICAL,
        'consumer defensive': MorningstarSectorCode.CONSUMER_DEFENSIVE,
        'energy': MorningstarSectorCode.ENERGY,
        'financial services': MorningstarSectorCode.FINANCIAL_SERVICES,
        'healthcare': MorningstarSectorCode.HEALTHCARE,
        'industrials': MorningstarSectorCode.INDUSTRIALS,
        'real estate': MorningstarSectorCode.REAL_ESTATE,
        'technology': MorningstarSectorCode.TECHNOLOGY,
        'utilities': MorningstarSectorCode.UTILITIES
    }

def str_to_bool(s):
    return str(s).strip().lower() in ["true", "1", "yes", "on"]