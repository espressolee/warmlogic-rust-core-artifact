import fs from 'fs';
import type { NextApiRequest, NextApiResponse } from 'next';
import path from 'path';

export default function handler(req: NextApiRequest, res: NextApiResponse) {
    const { id } = req.query; // 'id' will be the filename, e.g., 'repro_20260127_xxxx.wlid'

    if (!id || typeof id !== 'string') {
        return res.status(400).json({ error: 'Invalid bundle ID' });
    }

    // Assuming console is in warm_logic/console, root is ../../
    const bundlePath = path.resolve(process.cwd(), '../../ledger/bundles', id);

    try {
        if (!fs.existsSync(bundlePath)) {
            return res.status(404).json({ error: 'Bundle not found' });
        }

        const fileContent = fs.readFileSync(bundlePath, 'utf-8');
        const bundle = JSON.parse(fileContent);

        res.status(200).json({ bundle });
    } catch (error) {
        res.status(500).json({ error: 'Failed to read bundle' });
    }
}
