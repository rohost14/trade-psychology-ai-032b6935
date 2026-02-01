import unittest
from app.utils.trade_classifier import infer_asset_class, infer_instrument_type, classify_trade

class TestTradeClassifier(unittest.TestCase):
    
    def test_infer_asset_class(self):
        self.assertEqual(infer_asset_class('NSE'), 'EQUITY')
        self.assertEqual(infer_asset_class('BSE'), 'EQUITY')
        self.assertEqual(infer_asset_class('NFO'), 'EQUITY')
        self.assertEqual(infer_asset_class('BFO'), 'EQUITY')
        self.assertEqual(infer_asset_class('MCX'), 'COMMODITY')
        self.assertEqual(infer_asset_class('CDS'), 'FOREX')
        
        with self.assertRaises(ValueError):
            infer_asset_class('UNKNOWN')

    def test_infer_instrument_type(self):
        # Options
        self.assertEqual(infer_instrument_type('NIFTY24JAN21500CE', 'NFO'), 'OPTION')
        self.assertEqual(infer_instrument_type('BANKNIFTY24JAN45000PE', 'NFO'), 'OPTION')
        self.assertEqual(infer_instrument_type('CRUDEOIL24JAN7000CE', 'MCX'), 'OPTION') # Assuming commodities have options
        
        # Futures
        self.assertEqual(infer_instrument_type('NIFTY24JANFUT', 'NFO'), 'FUTURE')
        self.assertEqual(infer_instrument_type('CRUDEOIL24JANFUT', 'MCX'), 'FUTURE')
        self.assertEqual(infer_instrument_type('USDINR24JANFUT', 'CDS'), 'FUTURE')
        
        # Spot (Equity)
        self.assertEqual(infer_instrument_type('RELIANCE', 'NSE'), 'SPOT')
        self.assertEqual(infer_instrument_type('TCS', 'BSE'), 'SPOT')
        
        # Edge case: Symbol ending in CE/PE but on NSE (unlikely to be option, but per logic is OPTION?)
        # Logic update: NSE/BSE are Spot only. So even if it ends in CE/PE, it's SPOT (e.g. RELIANCE ends in CE).
        self.assertEqual(infer_instrument_type('PACE', 'NSE'), 'SPOT') 
        self.assertEqual(infer_instrument_type('RELIANCE', 'NSE'), 'SPOT')

    def test_classify_trade(self):
        # Equity Delivery
        trade1 = {
            'exchange': 'NSE',
            'tradingsymbol': 'INFY',
            'product': 'CNC'
        }
        res1 = classify_trade(trade1)
        self.assertEqual(res1['asset_class'], 'EQUITY')
        self.assertEqual(res1['instrument_type'], 'SPOT')
        self.assertEqual(res1['product_type'], 'CNC')
        
        # F&O Option
        trade2 = {
            'exchange': 'NFO',
            'tradingsymbol': 'NIFTY24JAN18000CE',
            'product': 'NRML'
        }
        res2 = classify_trade(trade2)
        self.assertEqual(res2['asset_class'], 'EQUITY')
        self.assertEqual(res2['instrument_type'], 'OPTION')
        self.assertEqual(res2['product_type'], 'NRML')
        
        # Commodity Future
        trade3 = {
            'exchange': 'MCX',
            'tradingsymbol': 'GOLDM24JANFUT',
            'product': 'MIS'
        }
        res3 = classify_trade(trade3)
        self.assertEqual(res3['asset_class'], 'COMMODITY')
        self.assertEqual(res3['instrument_type'], 'FUTURE')
        self.assertEqual(res3['product_type'], 'MIS')

if __name__ == '__main__':
    unittest.main()
