const crypto = require('crypto')
const qrcode = require('qrcode');
const base32Decode = require('base32-decode')
const base32Encode = require('base32-encode');
const { store } = require('./core');


function generateHOTP(secret, counter) {
  const decodedSecret = base32Decode(secret, 'RFC4648');

  const buffer = Buffer.alloc(8);
  for (let i = 0; i < 8; i++) {
    buffer[7 - i] = counter & 0xff;
    counter = counter >> 8;
  }

  // Step 1: Generate an HMAC-SHA-1 value
  const hmac = crypto.createHmac('sha1', Buffer.from(decodedSecret));
  hmac.update(buffer);
  const hmacResult = hmac.digest();

  // Step 2: Generate a 4-byte string (Dynamic Truncation)
  const offset = hmacResult[hmacResult.length - 1] & 0xf;
  const code =
    ((hmacResult[offset] & 0x7f) << 24) |
    ((hmacResult[offset + 1] & 0xff) << 16) |
    ((hmacResult[offset + 2] & 0xff) << 8) |
    (hmacResult[offset + 3] & 0xff);

  // Step 3: Compute an HOTP value
  return `${code % 10 ** 6}`.padStart(6, '0');
}

function generateTOTP(secret, window = 0) {
  const counter = Math.floor(Date.now() / 30000);
  return generateHOTP(secret, counter + window);
}

function verifyTOTP(token, secret, window = 1) {
  for (let errorWindow = -window; errorWindow <= +window; errorWindow++) {
    const totp = generateTOTP(secret, errorWindow);
    if (token === totp) {
      return true;
    }
  }
  return false;
}

function generateMfaQr(event, parameters) {
  const user = store.get('user') || {
    username: 'FreeUser',
    mfaEnabled: false,
    mfaSecret: null
  };
  // console.log('generate-mfa-qr:', user)
  // For security, we no longer show the QR code after is verified
  if (user.mfaEnabled) return;

  if (!user.mfaSecret) {
    // generate unique secret for user
    // this secret will be used to check the verification code sent by user
    const buffer = crypto.randomBytes(14);
    user.mfaSecret = base32Encode(buffer, 'RFC4648', { padding: false });
    // console.log('generated-mfa-qr', user);
    store.set('user', user);
  }
  const issuer = 'Blade\'s LedFx';
  const algorithm = 'SHA1';
  const digits = '6';
  const period = '30';
  const otpType = 'totp';
  const configUri = `otpauth://${otpType}/${issuer}:${user.username}?algorithm=${algorithm}&digits=${digits}&period=${period}&issuer=${issuer}&secret=${user.mfaSecret}`;

  qrcode.toDataURL(configUri, {
    color: { dark: '#333333FF', light: '#00000000' },
  }).then((png=>wind.webContents.send('fromMain', ['mfa-qr-code', png])));

  return;
}
function handleVerifyOTP(wind, event, parameters) {
  const user = store.get('user') || {
    username: 'FreeUser',
    mfaEnabled: false,
    mfaSecret: null
  }
  const token = parameters.token;
  const secret = user.mfaSecret;
  // console.log('verify_otp:', user)
  const verified = verifyTOTP(token, secret);
  if (verified) {
    user.mfaEnabled = true;
    store.set('user', user);
  }

  // console.log('verified_otp:', verified ,user)
  wind.webContents.send('fromMain', ['mfa-verified', verified]);
  return;
}

module.exports = { generateHOTP, generateTOTP, verifyTOTP, handleVerifyOTP, generateMfaQr };
