import fs from 'fs';
import type { NextApiRequest, NextApiResponse } from 'next';
import path from 'path';

export default function handler(req: NextApiRequest, res: NextApiResponse) {
    // Trace back from warm_logic/console/pages/api to root
    // Assuming console is in warm_logic/console, root is ../../
    const ledgerPath = path.resolve(process.cwd(), '../../ledger/refusal_spine.jsonl');

    try {
        if (!fs.existsSync(ledgerPath)) {
            return res.status(200).json({ events: [] });
        }

        const fileContent = fs.readFileSync(ledgerPath, 'utf-8');
        const events = fileContent
            .trim()
            .split('\n')
            .map(line => {
                try {
                    return JSON.parse(line);
                } catch (e) {
                    return null;
                }
            })
            .filter(Boolean)
            .reverse(); // Newest first

        res.status(200).json({ events });
    } catch (error) {
        res.status(500).json({ error: 'Failed to read ledger' });
    }
}
