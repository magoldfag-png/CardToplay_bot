
from yoomoney import Authorize

Authorize(
    client_id="F6C5C9243ECA1F673CCA7D1B09D8724BE5FFC9D46AE8BD218973127C5B5E571B",
    redirect_uri="https://t.me/CardPackToPlay_bot",
    client_secret="E4FDD045D74E67A9CE512E6415E8C992866E6EFCEB564E0D9896DA7FD030CE7E4AE8AAE6553FE7ECECFCD1FFFDA6C321E040B2F844D3CE3025C1D60C76947EDF",
    scope=["account-info", "operation-history", "operation-details", "incoming-transfers", "payment-p2p"]
)