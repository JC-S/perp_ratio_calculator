#!/usr/bin/env python3

import ccxt
from utils import bn_api_key, bn_api_secret, bb_api_key, bb_api_secret, bg_api_key, bg_api_secret, bg_passphrase, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from typing import Dict, List, Tuple
import argparse
import time
import schedule
import requests
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def log_api_response(response, description):
    logger.info(f"{description}: {response}")

def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        response = requests.post(url, data=payload, timeout=10)
        response.raise_for_status()
        response_json = response.json()
        
        log_api_response(response_json, "Telegram API Response")
        
        if not response_json.get("ok"):
            logger.error(
                f"Telegram API Error: {response_json.get('description')} (Error Code: {response_json.get('error_code')}) for message: {message[:100]}...")
            if response_json.get('error_code') == 429:
                retry_after = response_json.get('parameters', {}).get('retry_after')
                if retry_after and isinstance(retry_after, int) and retry_after > 0:
                    logger.warning(f"Telegram rate limit hit. Retrying after {retry_after} seconds.")
                    time.sleep(retry_after)
                    response_retry = requests.post(url, data=payload, timeout=10)
                    response_retry.raise_for_status()
                    response_retry_json = response_retry.json()
                    log_api_response(response_retry_json, "Telegram API Retry Response")
                    if response_retry_json.get("ok"):
                        logger.info(f"Message sent to Telegram successfully after retry: {message[:100]}...")
                    else:
                        logger.error(f"Telegram API Error on retry: {response_retry_json.get('description')}")
                else:
                    logger.warning("Telegram rate limit hit, but no valid retry_after. Not retrying immediately.")
        else:
            logger.info(f"Message sent to Telegram successfully: {message[:100]}...")
    except requests.exceptions.HTTPError as he:
        logger.error(f"HTTP Error when sending Telegram message: {he.response.status_code} - {he.response.text}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send Telegram message due to RequestException: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred in send_telegram_message: {e}", exc_info=True)

class PerpRatioCalculator:
    # Exchange alias mapping
    EXCHANGE_ALIASES = {
        'bn': 'binance',
        'bb': 'bybit', 
        'bg': 'bitget'
    }
    
    def __init__(self, exchange_name: str):
        # Handle aliases
        self.exchange_name = self.EXCHANGE_ALIASES.get(exchange_name.lower(), exchange_name.lower())
        self.exchange = self._initialize_exchange()
    
    def _clean_symbol(self, symbol: str) -> str:
        """Clean symbol name by removing redundant USDT/USDC suffixes"""
        # Remove :USDT or :USDC suffix if present
        if ':USDT' in symbol:
            symbol = symbol.split(':USDT')[0]
        elif ':USDC' in symbol:
            symbol = symbol.split(':USDC')[0]
        return symbol
        
    def _initialize_exchange(self):
        if self.exchange_name == 'binance':
            return ccxt.binance({
                'apiKey': bn_api_key,
                'secret': bn_api_secret,
                'sandbox': False,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future'
                }
            })
        elif self.exchange_name == 'bybit':
            return ccxt.bybit({
                'apiKey': bb_api_key,
                'secret': bb_api_secret,
                'sandbox': False,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'linear'
                }
            })
        elif self.exchange_name == 'bitget':
            return ccxt.bitget({
                'apiKey': bg_api_key,
                'secret': bg_api_secret,
                'password': bg_passphrase,
                'sandbox': False,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'swap'
                }
            })
        else:
            raise ValueError(f"Unsupported exchange: {self.exchange_name}")
    
    def fetch_positions(self) -> List[Dict]:
        try:
            positions = self.exchange.fetch_positions()
            return [pos for pos in positions if pos['contracts'] > 0]
        except Exception as e:
            print(f"Error fetching positions: {e}")
            return []
    
    def fetch_account_balance(self) -> Dict:
        try:
            balance = self.exchange.fetch_balance()
            # Get the total account value for futures trading
            if self.exchange_name == 'binance':
                # For Binance, we need the futures account balance
                total_wallet_balance = balance.get('info', {}).get('totalWalletBalance', 0)
                total_unrealized_pnl = balance.get('info', {}).get('totalUnrealizedProfit', 0)
                total_margin_balance = balance.get('info', {}).get('totalMarginBalance', 0)
                
                return {
                    'total_wallet_balance': float(total_wallet_balance) if total_wallet_balance else 0,
                    'total_unrealized_pnl': float(total_unrealized_pnl) if total_unrealized_pnl else 0,
                    'total_margin_balance': float(total_margin_balance) if total_margin_balance else 0
                }
            elif self.exchange_name == 'bybit':
                # For Bybit, we need the unified account balance
                total_equity = balance.get('info', {}).get('result', {}).get('list', [{}])[0].get('totalEquity', 0)
                total_wallet_balance = balance.get('info', {}).get('result', {}).get('list', [{}])[0].get('totalWalletBalance', 0)
                total_unrealized_pnl = balance.get('info', {}).get('result', {}).get('list', [{}])[0].get('totalPerpUPL', 0)
                
                return {
                    'total_wallet_balance': float(total_wallet_balance) if total_wallet_balance else 0,
                    'total_unrealized_pnl': float(total_unrealized_pnl) if total_unrealized_pnl else 0,
                    'total_margin_balance': float(total_equity) if total_equity else 0
                }
            elif self.exchange_name == 'bitget':
                # For Bitget, we need the futures account balance
                # Bitget balance structure is a list
                try:
                    # Try to get the balance information from the response
                    balance_info = balance.get('info', [])
                    if balance_info and isinstance(balance_info, list) and len(balance_info) > 0:
                        # Look for USDT balance
                        for asset_balance in balance_info:
                            if asset_balance.get('marginCoin') == 'USDT':
                                available = float(asset_balance.get('available', 0))
                                locked = float(asset_balance.get('locked', 0))
                                total_wallet_balance = available + locked
                                total_unrealized_pnl = float(asset_balance.get('unrealizedPL', 0))
                                total_margin_balance = float(asset_balance.get('accountEquity', total_wallet_balance))
                                
                                return {
                                    'total_wallet_balance': total_wallet_balance,
                                    'total_unrealized_pnl': total_unrealized_pnl,
                                    'total_margin_balance': total_margin_balance
                                }
                except:
                    pass
                return {'total_wallet_balance': 0, 'total_unrealized_pnl': 0, 'total_margin_balance': 0}
            else:
                return {'total_wallet_balance': 0, 'total_unrealized_pnl': 0, 'total_margin_balance': 0}
        except Exception as e:
            print(f"Error fetching account balance: {e}")
            return {'total_wallet_balance': 0, 'total_unrealized_pnl': 0, 'total_margin_balance': 0}
    
    def calculate_long_short_ratio(self, positions: List[Dict]) -> Dict:
        excluded_tickers = {'PAXGUSDT', 'BTCDOMUSDT', 'PAXG/USDT', 'BTCDOM/USDT', 'PAXG/USDT:USDT', 'BTCDOM/USDT:USDT'}
        
        # Group positions by symbol and net them
        symbol_positions = {}
        symbol_pnl = {}
        
        for pos in positions:
            symbol = pos['symbol']
            if symbol in excluded_tickers:
                continue
                
            notional = pos['notional']
            if notional is None:
                continue
                
            side = pos['side']
            # Get unrealized PNL
            unrealized_pnl = pos.get('unrealizedPnl', 0) or 0
            
            # For Bybit, adjust notional value with unrealized PNL
            if self.exchange_name == 'bybit':
                # For Bybit, the notional doesn't include PNL, so we need to adjust it
                # For long positions: actual exposure = notional + unrealized_pnl
                # For short positions: actual exposure = notional - unrealized_pnl (since PNL is negative for profitable shorts)
                if side == 'long':
                    notional_value = abs(notional) + unrealized_pnl
                elif side == 'short':
                    notional_value = -(abs(notional) - unrealized_pnl)
                else:
                    continue
            else:
                # For other exchanges, use notional as-is
                if side == 'long':
                    notional_value = abs(notional)
                elif side == 'short':
                    notional_value = -abs(notional)
                else:
                    continue
            
            if symbol not in symbol_positions:
                symbol_positions[symbol] = 0
                symbol_pnl[symbol] = 0
            symbol_positions[symbol] += notional_value
            symbol_pnl[symbol] += unrealized_pnl
        
        # Calculate raw long/short totals
        raw_long_total = 0
        raw_short_total = 0
        
        for symbol, net_notional in symbol_positions.items():
            if net_notional > 0:
                raw_long_total += net_notional
            elif net_notional < 0:
                raw_short_total += abs(net_notional)
        
        # Calculate effective long/short totals with BTC weighting
        effective_long_total = 0
        effective_short_total = 0
        
        for symbol, net_notional in symbol_positions.items():
            weight = 0.5 if symbol.startswith('BTC') else 1.0
            
            if net_notional > 0:
                effective_long_total += net_notional * weight
            elif net_notional < 0:
                effective_short_total += abs(net_notional) * weight
        
        # Calculate ratio
        if effective_short_total > 0:
            ratio = effective_long_total / effective_short_total
        else:
            ratio = float('inf') if effective_long_total > 0 else 0
        
        # Calculate overall PNL
        overall_pnl = sum(symbol_pnl.values())
        
        return {
            'raw_long_total': raw_long_total,
            'raw_short_total': raw_short_total,
            'effective_long_total': effective_long_total,
            'effective_short_total': effective_short_total,
            'long_short_ratio': ratio,
            'symbol_positions': symbol_positions,
            'symbol_pnl': symbol_pnl,
            'overall_pnl': overall_pnl
        }
    
    def run(self):
        logger.info(f"Fetching positions from {self.exchange_name}...")
        positions = self.fetch_positions()
        
        logger.info(f"Fetching account balance from {self.exchange_name}...")
        account_balance = self.fetch_account_balance()
        
        if not positions:
            logger.info("No positions found.")
            return None
        
        logger.info(f"Found {len(positions)} positions")
        
        results = self.calculate_long_short_ratio(positions)
        results['account_balance'] = account_balance
        
        # ANSI escape codes for colored formatting
        GREEN = '\033[92m'
        YELLOW = '\033[93m'
        CYAN = '\033[96m'
        RED = '\033[91m'
        RESET = '\033[0m'
        
        print("\n" + "="*60)
        print("PERPETUAL POSITIONS LONG/SHORT RATIO ANALYSIS")
        print("="*60)
        print(f"Exchange: {self.exchange_name.upper()}")
        print(f"Total positions analyzed: {len(positions)}")
        print(f"Excluded tickers: PAXGUSDT, BTCDOMUSDT")
        print(f"BTC weight factor: 0.5")
        
        print("\n" + "-"*40)
        print("ACCOUNT BALANCE")
        print("-"*40)
        print(f"Wallet Balance:        ${results['account_balance']['total_wallet_balance']:,.2f}")
        print(f"{CYAN}Margin Balance:        ${results['account_balance']['total_margin_balance']:,.2f}{RESET}")
        
        # Color PNL based on positive/negative
        pnl_value = results['account_balance']['total_unrealized_pnl']
        pnl_color = GREEN if pnl_value >= 0 else RED
        print(f"{pnl_color}Unrealized PNL:        ${pnl_value:,.2f}{RESET}")
        
        print("\n" + "-"*40)
        print("OVERALL NOTIONAL VALUES")
        print("-"*40)
        print(f"Raw Long Total:        ${results['raw_long_total']:,.2f}")
        print(f"Raw Short Total:       ${results['raw_short_total']:,.2f}")
        print(f"Effective Long Total:  ${results['effective_long_total']:,.2f}")
        print(f"Effective Short Total: ${results['effective_short_total']:,.2f}")
        
        # Color overall PNL based on positive/negative
        overall_pnl = results['overall_pnl']
        overall_pnl_color = GREEN if overall_pnl >= 0 else RED
        print(f"{overall_pnl_color}Overall PNL:           ${overall_pnl:,.2f}{RESET}")
        
        print("\n" + "-"*40)
        print("LONG/SHORT RATIO")
        print("-"*40)
        if results['long_short_ratio'] == float('inf'):
            print(f"{YELLOW}Long/Short Ratio: ∞ (no short positions){RESET}")
        else:
            print(f"{YELLOW}Long/Short Ratio: {results['long_short_ratio']:.4f}{RESET}")
        
        print("\n" + "-"*40)
        print("POSITION BREAKDOWN BY SYMBOL")
        print("-"*40)
        
        # Sort positions: long first, then short, sorted by notional
        long_positions = []
        short_positions = []
        
        for symbol, net_notional in results['symbol_positions'].items():
            pnl = results['symbol_pnl'].get(symbol, 0)
            if net_notional > 0:
                long_positions.append((symbol, net_notional, pnl))
            else:
                short_positions.append((symbol, net_notional, pnl))
        
        # Sort by notional value (descending for long, ascending for short)
        long_positions.sort(key=lambda x: x[1], reverse=True)
        short_positions.sort(key=lambda x: abs(x[1]), reverse=True)
        
        # Print long positions first
        if long_positions:
            print("LONG POSITIONS:")
            for symbol, net_notional, pnl in long_positions:
                clean_symbol = self._clean_symbol(symbol)
                pnl_color = GREEN if pnl >= 0 else RED
                pnl_str = f" | PNL: {pnl_color}${pnl:>9,.2f}{RESET}"
                print(f"  {clean_symbol:<15} LONG  ${abs(net_notional):>12,.2f}{pnl_str}")
        
        # Print short positions second
        if short_positions:
            if long_positions:
                print()
            print("SHORT POSITIONS:")
            for symbol, net_notional, pnl in short_positions:
                clean_symbol = self._clean_symbol(symbol)
                pnl_color = GREEN if pnl >= 0 else RED
                pnl_str = f" | PNL: {pnl_color}${pnl:>9,.2f}{RESET}"
                print(f"  {clean_symbol:<15} SHORT ${abs(net_notional):>12,.2f}{pnl_str}")
        
        return results
    
    def format_telegram_message(self, results: Dict) -> str:
        message = f"*{self.exchange_name.upper()} - Perpetual Positions Analysis*\n\n"
        
        # Account balance
        message += "*Account Balance:*\n"
        message += f"Wallet Balance: ${results['account_balance']['total_wallet_balance']:,.2f}\n"
        message += f"*Margin Balance: ${results['account_balance']['total_margin_balance']:,.2f}*\n"
        message += f"*Unrealized PNL: ${results['account_balance']['total_unrealized_pnl']:,.2f}*\n\n"
        
        # Overall stats
        message += "*Overall Stats:*\n"
        message += f"Raw Long: ${results['raw_long_total']:,.2f}\n"
        message += f"Raw Short: ${results['raw_short_total']:,.2f}\n"
        message += f"Effective Long: ${results['effective_long_total']:,.2f}\n"
        message += f"Effective Short: ${results['effective_short_total']:,.2f}\n"
        message += f"Overall PNL: ${results['overall_pnl']:,.2f}\n"
        
        # Long/Short ratio
        if results['long_short_ratio'] == float('inf'):
            message += f"*Long/Short Ratio: ∞*\n\n"
        else:
            message += f"*Long/Short Ratio: {results['long_short_ratio']:.4f}*\n\n"
        
        # Sort positions: long first, then short, sorted by notional
        long_positions = []
        short_positions = []
        
        for symbol, net_notional in results['symbol_positions'].items():
            pnl = results['symbol_pnl'].get(symbol, 0)
            if net_notional > 0:
                long_positions.append((symbol, net_notional, pnl))
            else:
                short_positions.append((symbol, net_notional, pnl))
        
        # Sort by notional value (descending for long, ascending for short)
        long_positions.sort(key=lambda x: x[1], reverse=True)
        short_positions.sort(key=lambda x: abs(x[1]), reverse=True)
        
        # Add long positions
        if long_positions:
            message += "*Long Positions:*\n"
            for symbol, notional, pnl in long_positions:
                clean_symbol = self._clean_symbol(symbol)
                message += f"`{clean_symbol:<12}` ${notional:>10,.2f} | PNL: ${pnl:>8,.2f}\n"
            message += "\n"
        
        # Add short positions
        if short_positions:
            message += "*Short Positions:*\n"
            for symbol, notional, pnl in short_positions:
                clean_symbol = self._clean_symbol(symbol)
                message += f"`{clean_symbol:<12}` ${abs(notional):>10,.2f} | PNL: ${pnl:>8,.2f}\n"
        
        return message

def run_both_exchanges():
    logger.info("Starting hourly analysis for all exchanges...")
    
    exchanges = ['binance', 'bybit', 'bitget']
    
    for i, exchange in enumerate(exchanges):
        try:
            calculator = PerpRatioCalculator(exchange)
            results = calculator.run()
            
            if results:
                telegram_message = calculator.format_telegram_message(results)
                send_telegram_message(telegram_message)
                logger.info(f"Successfully analyzed and sent report for {exchange}")
            else:
                logger.warning(f"No results from {exchange}")
                
        except Exception as e:
            logger.error(f"Error analyzing {exchange}: {e}", exc_info=True)
            error_message = f"*{exchange.upper()} - Error*\n\nFailed to fetch positions: {str(e)}"
            send_telegram_message(error_message)
            logger.info(f"Sent error report for {exchange}")
        
        # Add delay between exchanges to avoid rate limiting issues
        if i < len(exchanges) - 1:
            logger.info("Waiting 5 seconds before processing next exchange...")
            time.sleep(5)

def main():
    parser = argparse.ArgumentParser(description='Calculate long/short ratio for perpetual positions')
    parser.add_argument('-e', '--exchange', choices=['binance', 'bybit', 'bitget', 'bn', 'bb', 'bg'], default='binance',
                       help='Exchange to fetch positions from. Aliases: bn=binance, bb=bybit, bg=bitget (default: binance)')
    parser.add_argument('--daemon', action='store_true',
                       help='Run continuously and send hourly reports to Telegram')
    
    args = parser.parse_args()
    
    if args.daemon:
        logger.info("Starting daemon mode - will run analysis at the top of each hour and send to Telegram")
        
        # Schedule to run at the top of every hour (at minute 0)
        schedule.every().hour.at(":00").do(run_both_exchanges)
        
        logger.info("Scheduler started. Will run at the top of each hour. Press Ctrl+C to stop.")
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            logger.info("Daemon stopped by user")
    else:
        try:
            calculator = PerpRatioCalculator(args.exchange)
            calculator.run()
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()