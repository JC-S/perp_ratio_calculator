# Perpetual Positions Long/Short Ratio Calculator

A Python tool to calculate the long/short ratio of perpetual positions from cryptocurrency exchanges using the CCXT library.

## Features

- Fetches all perpetual positions from supported exchanges (Binance, Bybit, Bitget)
- Calculates accurate long/short ratios with advanced position netting
- Applies custom weighting for BTC positions (0.5x weight)
- Excludes specified tickers from calculations
- Provides comprehensive position analysis and breakdown
- **Automated hourly reporting via Telegram**
- **Runs continuously as a daemon process**
- **Sorted position display (long first, then short, by notional value)**

## Requirements

- Python 3.7+
- ccxt library
- schedule library (for daemon mode)
- requests library (for Telegram integration)
- Valid API keys for the chosen exchange
- Telegram bot token and chat ID (for automated reporting)

## Installation

1. Clone or download this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   
## Configuration

API keys and Telegram credentials are stored in `utils.py`:
- Binance: `bn_api_key`, `bn_api_secret`
- Bybit: `bb_api_key`, `bb_api_secret`
- Bitget: `bg_api_key`, `bg_api_secret`, `bg_passphrase`
- Telegram: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`

Make sure to update these with your actual API keys and Telegram credentials before running the script.

## Usage

### Basic Usage

```bash
# Single analysis - Use Binance (default)
python perp_ratio_calculator.py

# Single analysis - Use Bybit
python perp_ratio_calculator.py --exchange bybit

# Single analysis - Use Bitget
python perp_ratio_calculator.py --exchange bitget

# Continuous hourly reporting (daemon mode) - analyzes Binance and Bybit only
python perp_ratio_calculator.py --daemon
```

### Command Line Options

```bash
python perp_ratio_calculator.py --help
```

Options:
- `--exchange {binance,bybit,bitget}`: Choose the exchange for single analysis (default: binance)
- `--daemon`: Run continuously and send hourly reports to Telegram for Binance and Bybit exchanges

## Calculation Logic

### Position Netting
- For each ticker, long and short positions are netted against each other
- Example: 10,000 USDT long + 5,000 USDT short = 5,000 USDT net long

### Currency Valuation
- USDT and USDC positions are treated equally at $1 USD value

### BTC Weighting
- BTC positions receive a 0.5x weight factor
- Example: 10,000 USDT BTC long contributes 5,000 USDT to effective long total

### Exclusions
- PAXGUSDT and BTCDOMUSDT are excluded from all calculations

### Ratio Calculation
```
Long/Short Ratio = Effective Long Total / Effective Short Total
```

## Output

The script provides detailed information including:

1. **Overall Notional Values**
   - Raw Long/Short Totals (without BTC weighting)
   - Effective Long/Short Totals (with BTC weighting)

2. **Long/Short Ratio**
   - Final calculated ratio

3. **Position Breakdown**
   - Per-symbol breakdown showing net positions
   - Sorted by notional value (long positions first, then short positions)

### Telegram Reports

When running in daemon mode, the script sends formatted reports to Telegram every hour containing:
- Analysis for both Binance and Bybit exchanges (Bitget is not included in daemon mode)
- Clean formatting with markdown
- Sorted position lists (long first, then short, by notional value)
- Overall statistics and long/short ratios for each exchange

### Sample Output

```
============================================================
PERPETUAL POSITIONS LONG/SHORT RATIO ANALYSIS
============================================================
Exchange: BINANCE
Total positions analyzed: 15
Excluded tickers: PAXGUSDT, BTCDOMUSDT
BTC weight factor: 0.5

----------------------------------------
OVERALL NOTIONAL VALUES
----------------------------------------
Raw Long Total:        $125,000.00
Raw Short Total:       $85,000.00
Effective Long Total:  $115,000.00
Effective Short Total: $85,000.00

----------------------------------------
LONG/SHORT RATIO
----------------------------------------
Long/Short Ratio: 1.3529

----------------------------------------
POSITION BREAKDOWN BY SYMBOL
----------------------------------------
BTCUSDT         LONG  $   20,000.00 (weight: 0.5)
ETHUSDT         LONG  $   35,000.00
SOLUSDT         SHORT $   15,000.00
ADAUSDT         LONG  $   10,000.00
```

## Daemon Mode

When running with `--daemon` flag, the script:
- Analyzes both Binance and Bybit exchanges simultaneously (Bitget is excluded from daemon mode)
- Sends separate reports for each exchange to Telegram every hour
- Runs continuously until stopped with Ctrl+C
- Includes comprehensive logging for monitoring
- Handles API errors gracefully and continues running

## Error Handling

The script includes error handling for:
- Invalid API credentials
- Network connectivity issues
- Missing positions
- Exchange-specific errors
- Telegram API errors (with retry logic for rate limits)

## Security Notes

- Keep your API keys and Telegram credentials secure and never commit them to version control
- Use read-only API keys when possible
- Consider using environment variables for API keys and Telegram credentials in production
- Ensure your Telegram bot token has appropriate permissions

## Supported Exchanges

- **Binance**: Futures positions
- **Bybit**: Linear perpetual positions
- **Bitget**: Swap positions (normal mode only, not included in daemon mode)

## Troubleshooting

1. **"No positions found"**: Ensure you have open perpetual positions on the selected exchange
2. **API errors**: Verify your API keys are correct and have sufficient permissions
3. **Import errors**: Ensure all dependencies are installed (`pip install -r requirements.txt`)
4. **Telegram errors**: Verify your bot token and chat ID are correct
5. **Daemon mode not working**: Check that the virtual environment is activated and all dependencies are installed

## License

This project is provided as-is for educational and analytical purposes.