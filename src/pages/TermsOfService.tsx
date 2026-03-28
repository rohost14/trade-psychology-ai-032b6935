import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

const LAST_UPDATED = '17 March 2026';
const COMPANY = 'TradeMentor AI';
const CONTACT_EMAIL = 'legal@tradementor.ai';

export default function TermsOfService() {
  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-3xl mx-auto px-6 py-12">
        {/* Back link */}
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground mb-8"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </Link>

        <h1 className="text-3xl font-semibold text-foreground mb-2">Terms of Service</h1>
        <p className="text-sm text-muted-foreground mb-10">
          Last updated: {LAST_UPDATED} &nbsp;·&nbsp; Effective immediately upon account creation
        </p>

        <div className="prose prose-sm max-w-none space-y-8 text-foreground">

          {/* 1. Agreement */}
          <section>
            <h2 className="text-lg font-semibold mb-3">1. Agreement to Terms</h2>
            <p className="text-muted-foreground leading-relaxed">
              By accessing or using {COMPANY} ("the Platform", "we", "us"), you agree to be bound
              by these Terms of Service and our Privacy Policy. If you do not agree, do not use the
              Platform. These terms govern your use of the trading psychology analysis service
              provided through our web application.
            </p>
          </section>

          {/* 2. NOT Investment Advice — most important */}
          <section className="p-5 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-lg">
            <h2 className="text-lg font-semibold mb-3 text-amber-800 dark:text-amber-200">
              2. Important: Not Investment Advice
            </h2>
            <div className="space-y-3 text-amber-800 dark:text-amber-300 text-sm leading-relaxed">
              <p>
                <strong>{COMPANY} is NOT a SEBI-registered Investment Adviser (IA) or Research
                Analyst (RA)</strong> as defined under SEBI (Investment Advisers) Regulations, 2013
                or SEBI (Research Analysts) Regulations, 2014.
              </p>
              <p>
                The Platform provides <strong>behavioural analytics and trading psychology tools
                only</strong>. All information, AI-generated insights, pattern detections, alerts,
                and coaching content are intended to help you understand your own trading
                behaviour — they do not constitute:
              </p>
              <ul className="list-disc pl-5 space-y-1">
                <li>Investment advice or recommendations to buy, sell, or hold any security</li>
                <li>Research reports or research recommendations on any instrument</li>
                <li>Market analysis, price targets, or entry/exit levels</li>
                <li>Any form of financial planning advice</li>
              </ul>
              <p>
                <strong>All trading decisions are solely your responsibility.</strong> Past
                behavioural patterns shown by the Platform do not guarantee future trading outcomes.
                F&O trading involves significant risk of capital loss; you should consult a
                SEBI-registered adviser before making investment decisions.
              </p>
            </div>
          </section>

          {/* 3. Service Description */}
          <section>
            <h2 className="text-lg font-semibold mb-3">3. Description of Service</h2>
            <p className="text-muted-foreground leading-relaxed mb-3">
              {COMPANY} is a trading psychology platform that:
            </p>
            <ul className="list-disc pl-5 space-y-2 text-muted-foreground">
              <li>
                Connects to your Zerodha broker account via Zerodha's official KiteConnect API to
                read your trade history
              </li>
              <li>
                Analyses your trading behaviour to identify patterns such as overtrading, revenge
                trading, FOMO entries, and loss aversion
              </li>
              <li>
                Provides an AI-powered behavioural coach that discusses your trading psychology
                based on your actual trading data
              </li>
              <li>
                Sends optional end-of-day reports and morning briefings summarising your trading
                behaviour
              </li>
            </ul>
          </section>

          {/* 4. Broker Data */}
          <section>
            <h2 className="text-lg font-semibold mb-3">4. Broker Data & Third-Party Access</h2>
            <div className="space-y-3 text-muted-foreground leading-relaxed">
              <p>
                You authorise {COMPANY} to access your Zerodha account data (trades, positions,
                orders, profile) through Zerodha's KiteConnect API solely to provide the Platform's
                features. Your Zerodha credentials are never stored by us — authentication is
                handled entirely by Zerodha's OAuth 2.0 system.
              </p>
              <p>
                Your use of the Zerodha integration is also governed by Zerodha's own Terms of
                Service and KiteConnect API Terms. We are an independent third-party application,
                not affiliated with or endorsed by Zerodha Broking Limited.
              </p>
              <p>
                We do not share, sell, or transmit your trade data to any third party except as
                required to operate the Platform (e.g., AI inference via OpenRouter — your data is
                sent for analysis but not stored by the AI provider).
              </p>
            </div>
          </section>

          {/* 5. User Responsibilities */}
          <section>
            <h2 className="text-lg font-semibold mb-3">5. Your Responsibilities</h2>
            <ul className="list-disc pl-5 space-y-2 text-muted-foreground">
              <li>You must be at least 18 years old and legally capable of entering contracts in India</li>
              <li>You are solely responsible for all trading decisions and their financial consequences</li>
              <li>You must not use the Platform to violate any applicable laws, including SEBI regulations</li>
              <li>
                You must not attempt to reverse-engineer, scrape, or extract data from the Platform
                beyond normal use
              </li>
              <li>
                You acknowledge that behavioural insights are based on historical data and are not
                predictive of future performance
              </li>
            </ul>
          </section>

          {/* 6. Data & Privacy */}
          <section>
            <h2 className="text-lg font-semibold mb-3">6. Data & Privacy</h2>
            <p className="text-muted-foreground leading-relaxed">
              Our collection and use of your personal and financial data is governed by our{' '}
              <Link to="/privacy" className="text-primary underline">
                Privacy Policy
              </Link>
              , which is incorporated into these Terms by reference. By using the Platform, you
              consent to our data practices as described therein.
            </p>
          </section>

          {/* 7. Disclaimers & Limitation of Liability */}
          <section>
            <h2 className="text-lg font-semibold mb-3">7. Disclaimers & Limitation of Liability</h2>
            <div className="space-y-3 text-muted-foreground leading-relaxed">
              <p>
                <strong className="text-foreground">The Platform is provided "as is"</strong> without
                warranties of any kind, express or implied, including warranties of accuracy,
                completeness, or fitness for a particular purpose.
              </p>
              <p>
                Behavioural pattern detection is probabilistic. Alerts may be false positives or
                miss patterns entirely. Do not rely solely on the Platform for trading discipline —
                develop your own risk management systems.
              </p>
              <p>
                To the maximum extent permitted by applicable law, {COMPANY} shall not be liable for
                any direct, indirect, incidental, or consequential losses arising from your use of
                the Platform or from trading decisions made in reliance on it.
              </p>
            </div>
          </section>

          {/* 8. Account & Data Deletion */}
          <section>
            <h2 className="text-lg font-semibold mb-3">8. Account & Data Deletion</h2>
            <p className="text-muted-foreground leading-relaxed">
              You may disconnect your broker account and request deletion of your data at any time
              from the Settings page (Danger Zone section) or by emailing{' '}
              <a href={`mailto:${CONTACT_EMAIL}`} className="text-primary underline">
                {CONTACT_EMAIL}
              </a>
              . Upon deletion, all personally identifiable data will be permanently removed within
              30 days, except where retention is required by applicable law.
            </p>
          </section>

          {/* 9. Modifications */}
          <section>
            <h2 className="text-lg font-semibold mb-3">9. Modifications to Terms</h2>
            <p className="text-muted-foreground leading-relaxed">
              We may update these Terms from time to time. Material changes will be notified via
              in-app notification at least 7 days before taking effect. Continued use of the
              Platform after the effective date constitutes acceptance of the revised Terms.
            </p>
          </section>

          {/* 10. Governing Law */}
          <section>
            <h2 className="text-lg font-semibold mb-3">10. Governing Law</h2>
            <p className="text-muted-foreground leading-relaxed">
              These Terms are governed by the laws of India. Any disputes shall be subject to the
              exclusive jurisdiction of courts in Bengaluru, Karnataka. If any provision of these
              Terms is found invalid, the remaining provisions continue in full force.
            </p>
          </section>

          {/* Contact */}
          <section className="pt-4 border-t border-border">
            <h2 className="text-lg font-semibold mb-3">Contact</h2>
            <p className="text-muted-foreground">
              For questions about these Terms, contact us at{' '}
              <a href={`mailto:${CONTACT_EMAIL}`} className="text-primary underline">
                {CONTACT_EMAIL}
              </a>
              .
            </p>
          </section>

        </div>

        {/* Footer */}
        <div className="mt-12 pt-6 border-t border-border flex gap-4 text-sm text-muted-foreground">
          <Link to="/privacy" className="hover:text-foreground underline">Privacy Policy</Link>
          <Link to="/" className="hover:text-foreground">Back to App</Link>
        </div>
      </div>
    </div>
  );
}
