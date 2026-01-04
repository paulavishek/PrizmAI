"""
VPN/Proxy Detection Utility

Detects VPN, proxy, and datacenter IPs to prevent abuse.
This module provides multiple detection methods:
1. Local detection using IP ranges (free, fast, but limited)
2. Integration with external APIs (more accurate, has costs)

External API options:
- IPQualityScore (recommended)
- IP2Location
- MaxMind GeoIP
- IPHub
"""
import logging
import hashlib
import ipaddress
from functools import lru_cache
from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)

# Known VPN/Proxy provider IP ranges (partial list - datacenter IPs)
# These are common datacenter IP ranges that are often used by VPNs
KNOWN_DATACENTER_RANGES = [
    # AWS (commonly used by VPNs)
    "3.0.0.0/8",
    "52.0.0.0/8",
    "54.0.0.0/8",
    "18.0.0.0/8",
    # Google Cloud
    "35.0.0.0/8",
    "34.0.0.0/8",
    # Azure
    "40.0.0.0/8",
    "20.0.0.0/8",
    # DigitalOcean
    "104.131.0.0/16",
    "104.236.0.0/16",
    "138.68.0.0/16",
    "139.59.0.0/16",
    "167.99.0.0/16",
    "188.166.0.0/16",
    "206.189.0.0/16",
    # Linode
    "172.104.0.0/16",
    "173.230.0.0/16",
    "173.255.0.0/16",
    "192.155.0.0/16",
    "198.58.0.0/16",
    "45.56.0.0/16",
    "45.33.0.0/16",
    "50.116.0.0/16",
    "66.175.0.0/16",
    "69.164.0.0/16",
    "74.207.0.0/16",
    "96.126.0.0/16",
    # OVH
    "51.38.0.0/16",
    "51.68.0.0/16",
    "51.77.0.0/16",
    "51.79.0.0/16",
    "51.83.0.0/16",
    "51.89.0.0/16",
    "51.91.0.0/16",
    "54.36.0.0/16",
    "54.37.0.0/16",
    "54.38.0.0/16",
    # Vultr
    "45.32.0.0/16",
    "45.63.0.0/16",
    "45.76.0.0/16",
    "45.77.0.0/16",
    "66.42.0.0/16",
    "78.141.0.0/16",
    "95.179.0.0/16",
    "108.61.0.0/16",
    "140.82.0.0/16",
    "149.28.0.0/16",
    "155.138.0.0/16",
    "207.148.0.0/16",
    "209.222.0.0/16",
    "216.128.0.0/16",
    # Hetzner
    "116.202.0.0/16",
    "116.203.0.0/16",
    "135.181.0.0/16",
    "136.243.0.0/16",
    "138.201.0.0/16",
    "144.76.0.0/16",
    "148.251.0.0/16",
    "176.9.0.0/16",
    "178.63.0.0/16",
    "188.40.0.0/16",
    "195.201.0.0/16",
    "213.133.0.0/16",
    "213.239.0.0/16",
    "46.4.0.0/16",
    "5.9.0.0/16",
    "78.46.0.0/16",
    "85.10.0.0/16",
    "88.198.0.0/16",
    "88.99.0.0/16",
]

# Known VPN provider ASNs
KNOWN_VPN_ASNS = {
    'AS36351': 'SoftLayer (IBM Cloud)',
    'AS16276': 'OVH',
    'AS14061': 'DigitalOcean',
    'AS63949': 'Linode',
    'AS20473': 'Vultr',
    'AS24940': 'Hetzner',
    'AS16509': 'Amazon AWS',
    'AS15169': 'Google Cloud',
    'AS8075': 'Microsoft Azure',
    'AS9009': 'M247 (VPN Provider)',
    'AS9009': 'M247',
    'AS60068': 'Datacamp Limited (CDN77)',
    'AS202422': 'Private Internet Access VPN',
    'AS136787': 'NordVPN',
    'AS9009': 'M247 (ExpressVPN)',
    'AS212238': 'Mullvad VPN',
    'AS57858': 'Surfshark',
}

# Convert ranges to network objects for fast lookup
_datacenter_networks = None

def _get_datacenter_networks():
    """Lazy-load and cache network objects."""
    global _datacenter_networks
    if _datacenter_networks is None:
        _datacenter_networks = []
        for cidr in KNOWN_DATACENTER_RANGES:
            try:
                _datacenter_networks.append(ipaddress.ip_network(cidr))
            except ValueError as e:
                logger.warning(f"Invalid CIDR range: {cidr} - {e}")
    return _datacenter_networks


def is_datacenter_ip(ip_address: str) -> bool:
    """
    Check if an IP is from a known datacenter range.
    This is a fast local check without API calls.
    """
    try:
        ip = ipaddress.ip_address(ip_address)
        for network in _get_datacenter_networks():
            if ip in network:
                return True
        return False
    except ValueError:
        return False


def get_ip_risk_score(ip_address: str) -> Dict:
    """
    Calculate a local risk score for an IP address.
    Returns a score from 0-100 and risk factors.
    """
    score = 0
    factors = []
    
    if not ip_address:
        return {'score': 100, 'factors': ['No IP address']}
    
    try:
        ip = ipaddress.ip_address(ip_address)
        
        # Check if private IP (behind proxy)
        if ip.is_private:
            factors.append('Private IP (likely behind proxy)')
            score += 30
        
        # Check if datacenter IP
        if is_datacenter_ip(ip_address):
            factors.append('Datacenter IP range detected')
            score += 40
        
        # Check if reserved
        if ip.is_reserved:
            factors.append('Reserved IP range')
            score += 20
        
        # Check if loopback
        if ip.is_loopback:
            factors.append('Loopback address')
            score += 50
        
    except ValueError:
        factors.append('Invalid IP address format')
        score += 100
    
    return {
        'score': min(score, 100),
        'factors': factors,
        'is_suspicious': score >= 40,
    }


# API Integration Functions

def check_ip_with_ipqualityscore(ip_address: str) -> Optional[Dict]:
    """
    Check IP using IPQualityScore API.
    Requires IPQS_API_KEY in settings.
    
    Returns:
        {
            'fraud_score': 0-100,
            'is_vpn': bool,
            'is_proxy': bool,
            'is_tor': bool,
            'is_datacenter': bool,
            'is_bot': bool,
            'recent_abuse': bool,
            'country': str,
            'isp': str,
        }
    """
    api_key = getattr(settings, 'IPQS_API_KEY', None)
    if not api_key:
        logger.debug("IPQualityScore API key not configured")
        return None
    
    # Check cache first
    cache_key = f"ipqs_{hashlib.md5(ip_address.encode()).hexdigest()}"
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    try:
        import requests
        
        url = f"https://ipqualityscore.com/api/json/ip/{api_key}/{ip_address}"
        params = {
            'strictness': 1,
            'allow_public_access_points': True,
            'fast': True,
        }
        
        response = requests.get(url, params=params, timeout=5)
        data = response.json()
        
        if data.get('success'):
            result = {
                'fraud_score': data.get('fraud_score', 0),
                'is_vpn': data.get('vpn', False),
                'is_proxy': data.get('proxy', False),
                'is_tor': data.get('tor', False),
                'is_datacenter': data.get('is_crawler', False),
                'is_bot': data.get('bot_status', False),
                'recent_abuse': data.get('recent_abuse', False),
                'country': data.get('country_code', 'Unknown'),
                'isp': data.get('ISP', 'Unknown'),
                'organization': data.get('organization', 'Unknown'),
            }
            
            # Cache for 1 hour
            cache.set(cache_key, result, 3600)
            
            return result
    
    except Exception as e:
        logger.warning(f"IPQualityScore API error: {e}")
    
    return None


def check_ip_with_iphub(ip_address: str) -> Optional[Dict]:
    """
    Check IP using IPHub API.
    Requires IPHUB_API_KEY in settings.
    
    Returns:
        {
            'block': 0 (residential), 1 (non-residential), 2 (mixed),
            'is_vpn': bool,
            'country': str,
            'isp': str,
        }
    """
    api_key = getattr(settings, 'IPHUB_API_KEY', None)
    if not api_key:
        return None
    
    # Check cache
    cache_key = f"iphub_{hashlib.md5(ip_address.encode()).hexdigest()}"
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    try:
        import requests
        
        url = f"http://v2.api.iphub.info/ip/{ip_address}"
        headers = {'X-Key': api_key}
        
        response = requests.get(url, headers=headers, timeout=5)
        data = response.json()
        
        result = {
            'block': data.get('block', 0),
            'is_vpn': data.get('block', 0) == 1,
            'country': data.get('countryCode', 'Unknown'),
            'isp': data.get('isp', 'Unknown'),
            'asn': data.get('asn', ''),
        }
        
        # Cache for 1 hour
        cache.set(cache_key, result, 3600)
        
        return result
    
    except Exception as e:
        logger.warning(f"IPHub API error: {e}")
    
    return None


def comprehensive_ip_check(ip_address: str) -> Dict:
    """
    Perform comprehensive IP check using all available methods.
    Combines local checks with API checks if configured.
    
    Returns:
        {
            'ip_address': str,
            'risk_score': 0-100,
            'is_vpn': bool,
            'is_proxy': bool,
            'is_datacenter': bool,
            'is_suspicious': bool,
            'should_block': bool,
            'country': str,
            'isp': str,
            'factors': list,
            'api_used': str or None,
        }
    """
    result = {
        'ip_address': ip_address,
        'risk_score': 0,
        'is_vpn': False,
        'is_proxy': False,
        'is_datacenter': False,
        'is_suspicious': False,
        'should_block': False,
        'country': 'Unknown',
        'isp': 'Unknown',
        'factors': [],
        'api_used': None,
    }
    
    if not ip_address:
        result['risk_score'] = 100
        result['factors'].append('No IP address provided')
        result['should_block'] = True
        return result
    
    # Local check first
    local_result = get_ip_risk_score(ip_address)
    result['risk_score'] = local_result['score']
    result['factors'].extend(local_result['factors'])
    result['is_datacenter'] = is_datacenter_ip(ip_address)
    
    # Try IPQualityScore API
    ipqs_result = check_ip_with_ipqualityscore(ip_address)
    if ipqs_result:
        result['api_used'] = 'IPQualityScore'
        result['risk_score'] = max(result['risk_score'], ipqs_result['fraud_score'])
        result['is_vpn'] = ipqs_result['is_vpn']
        result['is_proxy'] = ipqs_result['is_proxy']
        result['is_datacenter'] = ipqs_result['is_datacenter'] or result['is_datacenter']
        result['country'] = ipqs_result['country']
        result['isp'] = ipqs_result['isp']
        
        if ipqs_result['is_vpn']:
            result['factors'].append('VPN detected (IPQS)')
        if ipqs_result['is_proxy']:
            result['factors'].append('Proxy detected (IPQS)')
        if ipqs_result['is_tor']:
            result['factors'].append('Tor exit node detected (IPQS)')
        if ipqs_result['recent_abuse']:
            result['factors'].append('Recent abuse reported (IPQS)')
    
    # Try IPHub as fallback
    if not ipqs_result:
        iphub_result = check_ip_with_iphub(ip_address)
        if iphub_result:
            result['api_used'] = 'IPHub'
            result['is_vpn'] = iphub_result['is_vpn']
            result['country'] = iphub_result['country']
            result['isp'] = iphub_result['isp']
            
            if iphub_result['is_vpn']:
                result['factors'].append('Non-residential IP detected (IPHub)')
                result['risk_score'] = max(result['risk_score'], 60)
    
    # Determine if suspicious/should block
    result['is_suspicious'] = result['risk_score'] >= 50 or result['is_vpn'] or result['is_proxy']
    result['should_block'] = result['risk_score'] >= 80
    
    return result


def should_require_additional_verification(ip_address: str) -> Tuple[bool, str]:
    """
    Determine if an IP should require additional verification (e.g., email, captcha).
    
    Returns:
        (requires_verification: bool, reason: str or None)
    """
    check_result = comprehensive_ip_check(ip_address)
    
    if check_result['should_block']:
        return True, "Your connection appears to be from a VPN or proxy. Please verify your email to continue."
    
    if check_result['is_vpn']:
        return True, "VPN detected. Please complete additional verification."
    
    if check_result['is_proxy']:
        return True, "Proxy detected. Please complete additional verification."
    
    if check_result['risk_score'] >= 60:
        return True, "Please complete additional verification to continue."
    
    return False, None


def get_vpn_detection_stats() -> Dict:
    """Get statistics about VPN detection configuration."""
    return {
        'local_datacenter_ranges': len(KNOWN_DATACENTER_RANGES),
        'known_vpn_asns': len(KNOWN_VPN_ASNS),
        'ipqs_configured': bool(getattr(settings, 'IPQS_API_KEY', None)),
        'iphub_configured': bool(getattr(settings, 'IPHUB_API_KEY', None)),
        'api_available': bool(getattr(settings, 'IPQS_API_KEY', None) or 
                            getattr(settings, 'IPHUB_API_KEY', None)),
    }


# Middleware integration helper
def check_request_ip(request) -> Dict:
    """
    Check the IP address from a Django request.
    Handles X-Forwarded-For headers.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip_address = x_forwarded_for.split(',')[0].strip()
    else:
        ip_address = request.META.get('REMOTE_ADDR', '')
    
    return comprehensive_ip_check(ip_address)
