1. automate with github action
2. use image from newsletter as playlist thumbnail
3. use first sentence from description from newsletter as playlist description
4. improve track parsing:
    * look for optional pipe (`|`) separating last song from artwork credits
    * add update date to description
5. switch secret management over to aws secrets manager or similar to enable automatic api token refreshes (spotify and gmail)
