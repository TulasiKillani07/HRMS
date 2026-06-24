"""
Notification utilities for sending emails and SMS
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.utils.logger import logger
from app.core.config import settings

async def send_invitation_email(email: str, admin_name: str, org_name: str, temp_password: str):
    """
    Send invitation email to new org admin
    
    Args:
        email: Admin email address
        admin_name: Admin full name
        org_name: Organization name
        temp_password: Temporary password
    """
    try:
        logger.info(f"Sending invitation email to {email} for organization {org_name}")
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'Welcome to {org_name} - HRMS Platform'
        msg['From'] = settings.GMAIL_USER
        msg['To'] = email
        
        # Create HTML content
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
                    <h2 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px;">
                        Welcome to HRMS Platform
                    </h2>
                    
                    <p>Hi <strong>{admin_name}</strong>,</p>
                    
                    <p>Your organization <strong>"{org_name}"</strong> has been successfully created in our HRMS platform.</p>
                    
                    <p>You have been assigned as the <strong>Organization Administrator</strong>.</p>
                    
                    <div style="background-color: #f8f9fa; padding: 15px; border-left: 4px solid #3498db; margin: 20px 0;">
                        <h3 style="margin-top: 0; color: #2c3e50;">Login Credentials:</h3>
                        <p style="margin: 5px 0;"><strong>Email:</strong> {email}</p>
                        <p style="margin: 5px 0;"><strong>Temporary Password:</strong> <code style="background-color: #fff; padding: 2px 6px; border-radius: 3px;">{temp_password}</code></p>
                    </div>
                    
                    <p style="color: #e74c3c;"><strong>⚠️ Important:</strong> Please login and change your password immediately for security purposes.</p>
                    
                    <p style="margin-top: 30px;">Best regards,<br><strong>HRMS Team</strong></p>
                    
                    <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
                    
                    <p style="font-size: 12px; color: #7f8c8d;">
                        This is an automated email. Please do not reply to this message.
                    </p>
                </div>
            </body>
        </html>
        """
        
        # Attach HTML content
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)
        
        # Send email via Gmail SMTP
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(settings.GMAIL_USER, settings.GMAIL_APP_PASSWORD)
            server.send_message(msg)
        
        logger.info(f"Invitation email sent successfully to {email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send invitation email to {email}: {str(e)}")
        return False

async def send_organization_welcome_email(org_email: str, org_name: str, admin_name: str, admin_email: str):
    """
    Send welcome email to organization
    
    Args:
        org_email: Organization email
        org_name: Organization name
        admin_name: Admin name
        admin_email: Admin email
    """
    try:
        logger.info(f"Sending welcome email to organization {org_name} at {org_email}")
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'{org_name} - Successfully Registered on HRMS Platform'
        msg['From'] = settings.GMAIL_USER
        msg['To'] = org_email
        
        # Create HTML content
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
                    <h2 style="color: #2c3e50; border-bottom: 2px solid #27ae60; padding-bottom: 10px;">
                        🎉 Organization Successfully Registered!
                    </h2>
                    
                    <p>Dear <strong>{org_name}</strong> Team,</p>
                    
                    <p>Congratulations! Your organization has been successfully registered on our HRMS platform.</p>
                    
                    <div style="background-color: #f8f9fa; padding: 15px; border-left: 4px solid #27ae60; margin: 20px 0;">
                        <h3 style="margin-top: 0; color: #2c3e50;">Organization Details:</h3>
                        <p style="margin: 5px 0;"><strong>Organization Name:</strong> {org_name}</p>
                        <p style="margin: 5px 0;"><strong>Organization Email:</strong> {org_email}</p>
                        <p style="margin: 5px 0;"><strong>Administrator:</strong> {admin_name}</p>
                        <p style="margin: 5px 0;"><strong>Admin Email:</strong> {admin_email}</p>
                    </div>
                    
                    <div style="background-color: #e8f8f5; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <h3 style="margin-top: 0; color: #27ae60;">✅ What's Next?</h3>
                        <ul style="margin: 10px 0; padding-left: 20px;">
                            <li>Your administrator has received login credentials via email</li>
                            <li>They can now access the HRMS platform and manage your organization</li>
                            <li>Start adding employees, departments, and managing payroll</li>
                            <li>Track attendance and manage leave requests</li>
                        </ul>
                    </div>
                    
                    <p>If you have any questions or need assistance, please don't hesitate to contact our support team.</p>
                    
                    <p style="margin-top: 30px;">Best regards,<br><strong>HRMS Team</strong></p>
                    
                    <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
                    
                    <p style="font-size: 12px; color: #7f8c8d;">
                        This is an automated email. Please do not reply to this message.
                    </p>
                </div>
            </body>
        </html>
        """
        
        # Attach HTML content
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)
        
        # Send email via Gmail SMTP
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(settings.GMAIL_USER, settings.GMAIL_APP_PASSWORD)
            server.send_message(msg)
        
        logger.info(f"Welcome email sent successfully to organization {org_name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send welcome email to {org_email}: {str(e)}")
        return False

async def send_notification_sms(phone: str, message: str):
    """
    Send SMS notification
    
    Args:
        phone: Phone number
        message: SMS message
    
    TODO: Integrate with SMS service (Twilio, AWS SNS, etc.)
    """
    logger.info(f"SMS notification to {phone}: {message}")
    logger.debug(f"""
    ====== SMS NOTIFICATION ======
    To: {phone}
    Message: {message}
    ==============================
    """)
    
    # TODO: Implement actual SMS sending
    # Example using Twilio:
    # from twilio.rest import Client
    # 
    # client = Client(account_sid, auth_token)
    # message = client.messages.create(
    #     body=message,
    #     from_='+1234567890',
    #     to=phone
    # )
    
    logger.info(f"SMS notification logged for {phone}")
    return True

async def notify_org_admin_created(admin_email: str, admin_name: str, admin_phone: str, 
                                   org_name: str, org_email: str, temp_password: str):
    """
    Send complete notification package when organization is created
    - Email to org admin with credentials
    - Email to organization with welcome message
    - SMS notification to admin
    """
    logger.info(f"Initiating notifications for organization: {org_name}")
    
    # Send invitation email to admin with credentials
    await send_invitation_email(admin_email, admin_name, org_name, temp_password)
    
    # Send welcome email to organization
    await send_organization_welcome_email(org_email, org_name, admin_name, admin_email)
    
    # Send SMS notification to admin
    sms_message = f"Welcome {admin_name}! Your {org_name} HRMS account is ready. Check your email at {admin_email} for login details."
    await send_notification_sms(admin_phone, sms_message)
    
    logger.info(f"All notifications sent for organization: {org_name}")
    return True

async def send_password_reset_otp(email: str, full_name: str, otp: str):
    """
    Send OTP email for password reset
    
    Args:
        email: User email address
        full_name: User full name
        otp: 6-digit OTP code
    """
    try:
        logger.info(f"Sending password reset OTP email to {email}")
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'Password Reset OTP - HRMS Platform'
        msg['From'] = settings.GMAIL_USER
        msg['To'] = email
        
        # Create HTML content
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
                    <h2 style="color: #2c3e50; border-bottom: 2px solid #e74c3c; padding-bottom: 10px;">
                        🔐 Password Reset Request
                    </h2>
                    
                    <p>Hi <strong>{full_name}</strong>,</p>
                    
                    <p>We received a request to reset your password for your HRMS account.</p>
                    
                    <div style="background-color: #fff3cd; padding: 20px; border-left: 4px solid #ffc107; margin: 20px 0; text-align: center;">
                        <p style="margin: 5px 0; font-size: 14px; color: #856404;">Your OTP Code:</p>
                        <h1 style="margin: 10px 0; font-size: 36px; letter-spacing: 8px; color: #2c3e50; font-family: 'Courier New', monospace;">
                            {otp}
                        </h1>
                        <p style="margin: 5px 0; font-size: 12px; color: #856404;">
                            This code will expire in <strong>10 minutes</strong>
                        </p>
                    </div>
                    
                    <div style="background-color: #f8d7da; padding: 15px; border-left: 4px solid #e74c3c; margin: 20px 0;">
                        <p style="margin: 0; color: #721c24;"><strong>⚠️ Security Notice:</strong></p>
                        <ul style="margin: 10px 0; padding-left: 20px; color: #721c24;">
                            <li>Never share this OTP with anyone</li>
                            <li>HRMS staff will never ask for your OTP</li>
                            <li>If you didn't request this, please ignore this email</li>
                        </ul>
                    </div>
                    
                    <p style="font-size: 14px; color: #7f8c8d; margin-top: 30px;">
                        If you didn't request a password reset, you can safely ignore this email. Your password will remain unchanged.
                    </p>
                    
                    <p style="margin-top: 30px;">Best regards,<br><strong>HRMS Team</strong></p>
                    
                    <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
                    
                    <p style="font-size: 12px; color: #7f8c8d;">
                        This is an automated email. Please do not reply to this message.
                    </p>
                </div>
            </body>
        </html>
        """
        
        # Attach HTML content
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)
        
        # Send email via Gmail SMTP
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(settings.GMAIL_USER, settings.GMAIL_APP_PASSWORD)
            server.send_message(msg)
        
        logger.info(f"Password reset OTP email sent successfully to {email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send password reset OTP email to {email}: {str(e)}")
        return False

async def send_password_reset_success(email: str, full_name: str):
    """
    Send confirmation email after successful password reset
    
    Args:
        email: User email address
        full_name: User full name
    """
    try:
        logger.info(f"Sending password reset success email to {email}")
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'Password Successfully Reset - HRMS Platform'
        msg['From'] = settings.GMAIL_USER
        msg['To'] = email
        
        # Create HTML content
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
                    <h2 style="color: #2c3e50; border-bottom: 2px solid #27ae60; padding-bottom: 10px;">
                        ✅ Password Successfully Reset
                    </h2>
                    
                    <p>Hi <strong>{full_name}</strong>,</p>
                    
                    <p>Your password has been successfully reset for your HRMS account.</p>
                    
                    <div style="background-color: #d4edda; padding: 15px; border-left: 4px solid #27ae60; margin: 20px 0;">
                        <p style="margin: 0; color: #155724;">
                            <strong>✓</strong> You can now login with your new password
                        </p>
                    </div>
                    
                    <div style="background-color: #f8d7da; padding: 15px; border-left: 4px solid #e74c3c; margin: 20px 0;">
                        <p style="margin: 0; color: #721c24;"><strong>⚠️ Security Alert:</strong></p>
                        <p style="margin: 10px 0 0 0; color: #721c24;">
                            If you didn't make this change, please contact support immediately as your account may be compromised.
                        </p>
                    </div>
                    
                    <p style="margin-top: 30px;">Best regards,<br><strong>HRMS Team</strong></p>
                    
                    <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
                    
                    <p style="font-size: 12px; color: #7f8c8d;">
                        This is an automated email. Please do not reply to this message.
                    </p>
                </div>
            </body>
        </html>
        """
        
        # Attach HTML content
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)
        
        # Send email via Gmail SMTP
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(settings.GMAIL_USER, settings.GMAIL_APP_PASSWORD)
            server.send_message(msg)
        
        logger.info(f"Password reset success email sent successfully to {email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send password reset success email to {email}: {str(e)}")
        return False


async def send_employee_welcome_email(
    email: str,
    first_name: str,
    org_name: str,
    temp_password: str
):
    """
    Send welcome onboarding email to new employee with login credentials.
    """
    try:
        logger.info(f"Sending employee welcome email to {email}")

        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'Welcome to {org_name} — Complete Your Onboarding'
        msg['From'] = settings.GMAIL_USER
        msg['To'] = email

        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
                    <h2 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px;">
                        👋 Welcome to {org_name}!
                    </h2>

                    <p>Hi <strong>{first_name}</strong>,</p>

                    <p>We're excited to have you on board! Your employee account has been created.</p>
                    <p>Please log in and complete your onboarding profile to get started.</p>

                    <div style="background-color: #f8f9fa; padding: 15px; border-left: 4px solid #3498db; margin: 20px 0;">
                        <h3 style="margin-top: 0; color: #2c3e50;">Your Login Credentials:</h3>
                        <p style="margin: 5px 0;"><strong>Email:</strong> {email}</p>
                        <p style="margin: 5px 0;"><strong>Temporary Password:</strong>
                            <code style="background-color: #fff; padding: 2px 8px; border-radius: 3px; font-size: 16px;">{temp_password}</code>
                        </p>
                    </div>

                    <div style="background-color: #e8f8f5; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <h3 style="margin-top: 0; color: #27ae60;">📋 Onboarding Checklist:</h3>
                        <ul style="margin: 10px 0; padding-left: 20px;">
                            <li>Personal Details</li>
                            <li>Address</li>
                            <li>Emergency Contact</li>
                            <li>Bank Details</li>
                            <li>Government IDs (PAN, Aadhaar)</li>
                            <li>Education</li>
                            <li>Experience</li>
                            <li>Upload Documents</li>
                            <li>Accept Company Policies</li>
                        </ul>
                    </div>

                    <p style="color: #e74c3c;">
                        <strong>⚠️ Important:</strong> Please change your password immediately after logging in.
                    </p>

                    <p style="margin-top: 30px;">Best regards,<br><strong>{org_name} HR Team</strong></p>

                    <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
                    <p style="font-size: 12px; color: #7f8c8d;">This is an automated email. Please do not reply.</p>
                </div>
            </body>
        </html>
        """

        msg.attach(MIMEText(html_content, 'html'))

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(settings.GMAIL_USER, settings.GMAIL_APP_PASSWORD)
            server.send_message(msg)

        logger.info(f"Employee welcome email sent to {email}")
        return True

    except Exception as e:
        logger.error(f"Failed to send employee welcome email to {email}: {str(e)}")
        return False


async def send_onboarding_revision_email(
    email: str,
    first_name: str,
    org_name: str,
    sections: list,
    notes: str = None
):
    """Notify employee that HR has requested changes to specific onboarding sections."""
    try:
        logger.info(f"Sending onboarding revision email to {email}")

        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'Action Required — Update Your Onboarding Details'
        msg['From'] = settings.GMAIL_USER
        msg['To'] = email

        sections_html = "".join(
            f"<li style='margin: 4px 0;'>{s.replace('_', ' ').title()}</li>"
            for s in sections
        )
        notes_html = (
            f"<div style='background:#fff3cd;padding:12px;border-left:4px solid #ffc107;margin:16px 0;'>"
            f"<strong>HR Notes:</strong> {notes}</div>"
            if notes else ""
        )

        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
                    <h2 style="color: #e74c3c; border-bottom: 2px solid #e74c3c; padding-bottom: 10px;">
                        🔄 Onboarding Update Required
                    </h2>
                    <p>Hi <strong>{first_name}</strong>,</p>
                    <p>HR has reviewed your onboarding profile and requested updates to the following sections:</p>
                    <ul style="padding-left: 20px; color: #e74c3c;">{sections_html}</ul>
                    {notes_html}
                    <p>Please log in and update the highlighted sections at your earliest convenience.</p>
                    <p style="margin-top: 30px;">Best regards,<br><strong>{org_name} HR Team</strong></p>
                    <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
                    <p style="font-size: 12px; color: #7f8c8d;">This is an automated email. Please do not reply.</p>
                </div>
            </body>
        </html>
        """

        msg.attach(MIMEText(html_content, 'html'))

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(settings.GMAIL_USER, settings.GMAIL_APP_PASSWORD)
            server.send_message(msg)

        logger.info(f"Onboarding revision email sent to {email}")
        return True

    except Exception as e:
        logger.error(f"Failed to send onboarding revision email to {email}: {str(e)}")
        return False
