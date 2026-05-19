Trigger ficha enrichment for a product SKU or internal product ID.

Arguments: `$ARGUMENTS`
- Required: SKU or product ID to enrich (e.g. `SKU-12345` or a UUID)

Steps:
1. Look up the product in the database or codebase to confirm it exists:
   - Check `mt-pricing-backend/app/services/ficha_enrichment/` for the enrichment pipeline entry point
   - The pipeline is: extractor → series_resolver → applier → model_writer → document_saver → product_creator
2. Run the enrichment via the API endpoint (if backend is running):
   ```
   curl -s -X POST http://localhost:8000/api/v1/ficha-enrich \
     -H "Content-Type: application/json" \
     -d '{"product_id": "$ARGUMENTS"}'
   ```
   Or identify the correct route from `mt-pricing-backend/app/api/routes/ficha_enrich.py` and use it.
3. Report: enrichment result, any fields populated, any warnings (missing family_id, brand_id, etc.)
4. If the product is not found, say so clearly and suggest checking the SKU format.

Note: All data extracted and saved to DB must be in English (except `translations` array entries).
