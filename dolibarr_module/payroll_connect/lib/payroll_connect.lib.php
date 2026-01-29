<?php
class PayrollConnectHelper
{
    /**
     * Sends a payload to the Django Webhook
     *
     * @param string $webhook_url URL configured in setup
     * @param string $api_secret  Secret configured in setup
     * @param array  $data        Data to send
     * @return bool|string Result
     */
    public static function sendToDjango($webhook_url, $api_secret, $data)
    {
        global $db, $conf, $mysoc;

        if (empty($webhook_url) || empty($api_secret)) {
            return false; // Not configured
        }

        $json_payload = json_encode($data);

        // Calculate HMAC-SHA256 Signature
        $signature = hash_hmac('sha256', $json_payload, $api_secret);

        $professional_id_1 = $mysoc->idprof1;

        // Curl Setup
        $ch = curl_init($webhook_url);
        curl_setopt($ch, CURLOPT_CUSTOMREQUEST, "POST");
        curl_setopt($ch, CURLOPT_POSTFIELDS, $json_payload);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);

        // Headers
        $headers = array(
            'Content-Type: application/json',
            'Content-Length: ' . strlen($json_payload),
            'X-Dolibarr-Signature: ' . $signature,
            'X-Dolibarr-Professional-ID: ' . $professional_id_1
        );
        curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
        curl_setopt($ch, CURLOPT_TIMEOUT, 5);

        $result = curl_exec($ch);
        $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        dol_syslog("Payroll Connect: Sent webhook to $webhook_url. Result Code: $http_code");

        return $result;
    }
}
?>