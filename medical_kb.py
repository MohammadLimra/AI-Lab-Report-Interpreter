import re

GUIDELINES = [
    {
        "id": "cholesterol",
        "title": "Cholesterol and Lipids (Dyslipidemia)",
        "keywords": ["cholesterol", "ldl", "hdl", "triglycerides", "lipid", "lipids", "vldl", "heart", "cardiac"],
        "content": """
- **Dietary Adjustments**: Focus on heart-healthy fats. Significantly reduce saturated fats (found in fatty meats, butter, cheese, and palm oil) and avoid trans fats entirely. Increase soluble fiber (oats, barley, beans, lentils, Brussels sprouts, apples, pears), which helps lower LDL ("bad") cholesterol absorption. Incorporate omega-3 fatty acids (fatty fish like salmon, flaxseeds, walnuts).
- **Physical Activity**: Regular cardiovascular exercise helps raise HDL ("good") cholesterol and lower LDL and triglycerides. Target at least 30 minutes of moderate-intensity exercise (e.g., brisk walking, cycling, swimming) 5 days a week.
- **Lifestyle Modifications**: If you smoke, quitting smoking is critical as it improves HDL levels and decreases overall cardiac risk. Limit alcohol consumption, as high intake can raise triglycerides and blood pressure.
- **Weight Management**: Losing even 5% to 10% of excess body weight can significantly improve your lipid profile.
- **Medical Follow-up**: Consult a doctor to determine if cholesterol-lowering medication (such as statins) is recommended based on your overall cardiovascular risk profile.
        """
    },
    {
        "id": "glucose_hba1c",
        "title": "Blood Glucose & HbA1c (Diabetes / Prediabetes)",
        "keywords": ["glucose", "hba1c", "blood sugar", "sugar", "diabetes", "diabetic", "insulin", "hba1c%", "glycated"],
        "content": """
- **Dietary Adjustments**: Focus on low-glycemic index (GI) foods. Significantly reduce refined carbohydrates, sugary beverages, sweets, white bread, and white rice. Increase intake of non-starchy vegetables (spinach, broccoli, cauliflower), whole grains (oats, quinoa), lean proteins (chicken, fish, tofu), and healthy fats (avocado, nuts).
- **Physical Activity**: Aim for at least 150 minutes of moderate-intensity aerobic exercise per week (e.g., brisk walking, cycling) combined with strength training 2-3 times weekly. Exercise helps muscles absorb glucose and improves insulin sensitivity.
- **Weight Management**: If overweight, losing even 5-10% of body weight can dramatically improve blood sugar control.
- **Monitoring**: Check blood glucose levels regularly as advised by your healthcare provider. Keep a log of meals and glucose readings to identify patterns.
- **Lifestyle**: Ensure 7-8 hours of sleep per night, as sleep deprivation negatively affects insulin sensitivity. Manage stress through meditation, deep breathing, or yoga, as stress hormones like cortisol raise blood glucose.
- **Medical Follow-up**: Work closely with your physician to adjust medications (like metformin or insulin) and screen for long-term complications.
        """
    },
    {
        "id": "hemoglobin_anemia",
        "title": "Hemoglobin, Red Blood Cells & Iron (Anemia)",
        "keywords": ["hemoglobin", "hb", "rbc", "iron", "ferritin", "anemia", "anemic", "red blood", "mcv", "mch", "mchc"],
        "content": """
- **Dietary Adjustments**: Focus on iron-rich foods. Heme iron (highly absorbed) is found in lean red meats, poultry, and fish. Non-heme iron is found in beans, lentils, spinach, fortified cereals, and pumpkin seeds. Always pair non-heme iron with Vitamin C (citrus fruits, bell peppers, strawberries) to dramatically increase iron absorption.
- **Foods/Drinks to Avoid**: Avoid drinking tea, coffee, or calcium-rich milk with iron-rich meals, as tannins, polyphenols, and calcium inhibit iron absorption.
- **Supplementation**: If diagnosed with iron-deficiency anemia, oral iron supplements may be prescribed by a physician. Take them as directed, noting they can cause dark stools and mild digestive discomfort.
- **Vitamin B12 & Folate**: Anemia can also be caused by B12 or folate deficiencies. Ensure adequate intake of leafy greens (folate) and animal products or fortified foods (B12).
- **Medical Follow-up**: Consult your doctor to identify the underlying cause of low hemoglobin (e.g., nutritional deficiency, blood loss, chronic inflammation).
        """
    },
    {
        "id": "liver_enzymes",
        "title": "Liver Enzymes (ALT, AST, Bilirubin, ALP, SGPT, SGOT)",
        "keywords": ["alt", "ast", "bilirubin", "alp", "sgpt", "sgot", "liver", "hepatic", "enzyme", "enzymes"],
        "content": """
- **Dietary Adjustments**: Adopt a liver-friendly Mediterranean diet rich in vegetables, fruits, whole grains, and healthy fats (olive oil). Limit processed foods, high-fructose corn syrup, and saturated fats to prevent fat accumulation in the liver.
- **Avoid Toxins**: Eliminate or drastically reduce alcohol consumption, which is a direct liver toxin. Avoid unnecessary or high doses of medications, including over-the-counter painkillers like acetaminophen (paracetamol), and consult a doctor before taking herbal supplements, as some can cause liver toxicity.
- **Exercise**: Regular physical activity helps reduce liver fat and improves liver health.
- **Medical Follow-up**: Elevated liver enzymes indicate liver irritation or damage. A physician should evaluate for fatty liver disease, viral hepatitis, medication side effects, or gallbladder issues.
        """
    },
    {
        "id": "kidney_markers",
        "title": "Kidney Function (Creatinine, Urea, BUN, GFR, EGFR)",
        "keywords": ["creatinine", "urea", "bun", "gfr", "egfr", "kidney", "renal", "filtration"],
        "content": """
- **Dietary Adjustments**: Manage protein intake, as processing protein creates urea and puts extra strain on the kidneys. Limit high-sodium foods to help control blood pressure. If kidney function is significantly impaired, a doctor may advise limiting potassium-rich foods (bananas, potatoes) and phosphorus-rich foods (dairy, cola).
- **Hydration**: Stay appropriately hydrated. Drink water throughout the day, but avoid over-hydration. Consult your doctor for fluid intake guidelines if you have advanced kidney or heart disease.
- **Medications to Avoid**: Strictly avoid NSAIDs (Non-Steroidal Anti-Inflammatory Drugs like ibuprofen, naproxen, diclofenac), as they directly decrease blood flow to the kidneys and can cause acute kidney injury.
- **Manage Underlying Conditions**: Keep blood pressure (ideally <130/80) and blood sugar tightly controlled, as hypertension and diabetes are the leading causes of chronic kidney damage.
- **Medical Follow-up**: High creatinine or low GFR requires medical evaluation to check for acute or chronic kidney disease.
        """
    },
    {
        "id": "thyroid",
        "title": "Thyroid Function (TSH, Free T3, Free T4)",
        "keywords": ["tsh", "t3", "t4", "thyroid", "thyroxine", "triiodothyronine", "hypothyroidism", "hyperthyroidism"],
        "content": """
- **Medication Consistency**: If prescribed thyroid medication (e.g., levothyroxine for hypothyroidism), take it daily on an empty stomach with a full glass of water, at least 30-60 minutes before breakfast. Avoid taking it at the same time as calcium, iron supplements, or antacids, which impair absorption.
- **Dietary Factors**: Ensure adequate but not excessive iodine intake (from iodized salt and seafood). For those with autoimmune thyroid issues, discuss soy or cruciferous vegetable intake with a dietitian.
- **Regular Monitoring**: Thyroid hormone levels fluctuate. Expect blood tests every 6-8 weeks after medication changes, and then annually once stabilized.
- **Medical Follow-up**: TSH levels outside the normal range require a physician's evaluation to diagnose hypothyroidism (high TSH, low T4) or hyperthyroidism (low TSH, high T4).
        """
    },
    {
        "id": "wbc_infection",
        "title": "White Blood Cells & Immune Response (WBC, Lymphocytes, Neutrophils)",
        "keywords": ["wbc", "white blood", "lymphocytes", "neutrophils", "monocytes", "eosinophils", "basophils", "infection", "immune", "leukocytes"],
        "content": """
- **Understand the Results**: High White Blood Cell (WBC) counts (leukocytosis) often indicate the body is fighting an infection, experiencing physical stress, or has inflammation. Low WBC counts (leukopenia) can indicate viral infections, autoimmune conditions, bone marrow issues, or medication side effects.
- **Infection Recovery**: If the elevation is due to an infection, prioritize rest, stay well-hydrated, and consume immune-supporting foods (rich in Vitamin C, zinc, and antioxidants).
- **Hygiene practices**: If WBC count is low, practice strict hygiene (frequent handwashing, avoiding crowds and sick individuals) to prevent infection.
- **Medical Follow-up**: Elevated or depressed WBC counts should be correlated with symptoms (fever, cough, pain). Do not take antibiotics without a prescription, as they only treat bacterial infections, not viral ones.
        """
    },
    {
        "id": "vitamin_d",
        "title": "Vitamin D (Calcidiol)",
        "keywords": ["vitamin d", "vit d", "25-hydroxy", "calcidiol", "d3", "d2", "cholecalciferol"],
        "content": """
- **Diet and Sunlight**: Vitamin D is synthesized by the skin in response to sunlight. Spend 10-15 minutes in midday sun (face, arms, or back) a few times a week without sunscreen (being mindful of skin safety). Dietary sources include fatty fish, egg yolks, and fortified foods (milk, orange juice, cereals).
- **Supplementation**: Vitamin D3 (cholecalciferol) supplements are highly effective. For severe deficiency (typically <20 ng/mL), a doctor may prescribe a high-dose weekly supplement (e.g., 50,000 IU) for 8-12 weeks, followed by a daily maintenance dose (800-2000 IU).
- **Calcium Synergy**: Vitamin D helps your body absorb calcium. Ensure you consume adequate calcium through dairy, leafy greens, or supplements.
- **Medical Follow-up**: Recheck Vitamin D levels after 3 months of supplementation to verify normal ranges have been restored.
        """
    },
    {
        "id": "vitamin_b12",
        "title": "Vitamin B12 (Cobalamin)",
        "keywords": ["b12", "vitamin b12", "cobalamin", "cyanocobalamin", "methylcobalamin"],
        "content": """
- **Dietary Sources**: Vitamin B12 is found naturally in animal products, including red meat, poultry, fish, eggs, milk, and cheese. Vegetarians and vegans should consume fortified foods (plant milks, breakfast cereals, nutritional yeast) or take regular supplements.
- **Supplementation**: For mild deficiency, daily oral B12 supplements are effective. For severe deficiency or absorption issues (like pernicious anemia, Crohn's disease, or post-gastric surgery), a doctor may prescribe intramuscular B12 injections.
- **Medication Interactions**: Long-term use of certain medications, such as metformin (for diabetes) or PPIs (acid reducers like omeprazole), can interfere with B12 absorption.
- **Medical Follow-up**: Low B12 can cause neurological symptoms (tingling, numbness, fatigue) and anemia. Consult a physician for an appropriate dosage and monitoring plan.
        """
    },
    {
        "id": "uric_acid",
        "title": "Uric Acid (Gout Management)",
        "keywords": ["uric acid", "urate", "gout", "joint pain", "joints"],
        "content": """
- **Dietary Adjustments**: Limit foods high in purines, which break down into uric acid. These include red meat, organ meats (liver, kidneys), seafood (sardines, anchovies, shellfish), and yeast extracts. Avoid high-fructose corn syrup (found in sodas and processed foods) and limit alcohol, especially beer, which is strongly associated with gout flare-ups.
- **Hydration**: Drink plenty of fluids (mainly water)—aim for 2 to 3 liters daily. Hydration helps dilate and flush uric acid out through the kidneys.
- **Weight and Metabolic Health**: Gradual weight loss helps reduce uric acid levels, but avoid crash diets or fasting, which can temporarily spike uric acid.
- **Medical Follow-up**: If you experience painful, swollen joints (often the big toe), consult a physician. Long-term uric acid management may require medications like allopurinol to prevent gout attacks and kidney stones.
        """
    },
    {
        "id": "hypertension",
        "title": "Blood Pressure & Hypertension Control",
        "keywords": ["blood pressure", "bp", "hypertension", "systolic", "diastolic"],
        "content": """
- **Dietary Adjustments**: Adopt the DASH (Dietary Approaches to Stop Hypertension) diet, emphasizing vegetables, fruits, whole grains, and low-fat dairy. Dramatically reduce sodium (salt) intake to less than 2,000 mg per day (ideally 1,500 mg) by avoiding processed foods, canned soups, and adding salt at the table.
- **Exercise**: Regular aerobic exercise (like brisk walking 30-40 minutes most days) relaxes blood vessels and lowers blood pressure.
- **Stress Management**: Practice stress-reduction techniques (mindfulness, yoga, deep-breathing exercises), as chronic stress spikes blood pressure.
- **Limit Stimulants**: Limit caffeine and alcohol intake, and quit smoking.
- **Medical Follow-up**: Check blood pressure regularly at home and keep a log. Consistent readings above 130/80 mmHg should be evaluated by a physician for potential antihypertensive medication management.
        """
    }
]

GENERAL_GUIDELINE = {
    "id": "general",
    "title": "General Health & Lab Report Interpretation",
    "keywords": ["help", "reduce", "increase", "what to do", "abnormal", "high", "low", "levels", "improve", "test"],
    "content": """
- **Review the Reference Ranges**: Lab values are interpreted based on the specific laboratory's normal range listed next to your results. A slight variance outside this range is common and may not be clinically significant.
- **Focus on Trends**: A single abnormal test is often a snapshot. Doctors look at trends over time and combinations of related tests rather than individual numbers in isolation.
- **Lifestyle Foundations**: Most mild elevations or deficiencies benefit from foundational lifestyle changes: eating a balanced diet rich in whole foods, staying physically active, maintaining healthy sleep habits, managing stress, and staying hydrated.
- **Consult a Professional**: Always discuss your complete report with your primary care provider. Do not alter current medication doses or start heavy supplementation without their explicit guidance.
    """
}

def retrieve_guidelines(query: str, report_text: str = "") -> list:
    """
    RAG Retrieval Algorithm.
    Calculates keyword-matching scores for each guideline in the database using 
    substring and boundary-based pattern matching, and returns the top relevant 
    clinical guidelines.
    """
    if not query:
        return []
    
    query_lower = query.lower()
    report_lower = report_text.lower() if report_text else ""
    
    scored_guidelines = []
    
    for guide in GUIDELINES:
        score = 0.0
        
        for kw in guide["keywords"]:
            kw_lower = kw.lower()
            pattern = r'\b' + re.escape(kw_lower) + r'\b'
            
            
            if re.search(pattern, query_lower):
                score += 4.0
            elif kw_lower in query_lower:
                score += 2.0
                
            
            if report_lower:
                if re.search(pattern, report_lower):
                    score += 1.0
                elif kw_lower in report_lower:
                    score += 0.5
                
        if score > 0:
            scored_guidelines.append((score, guide))
            
    
    scored_guidelines.sort(key=lambda x: x[0], reverse=True)
    
    results = [guide for score, guide in scored_guidelines]
    
    
    if not results or (len(results) == 1 and scored_guidelines[0][0] < 1.5):
        results.append(GENERAL_GUIDELINE)
        
    
    return results[:3]
