<?php

declare(strict_types=1);

namespace NxTutors\DemoCommandCenterAdapter\Tests\Feature;

use NxTutors\DemoCommandCenterAdapter\Tests\TestCase;

final class TutorProjectionTest extends TestCase
{
    public function testTutorProjectionNormalizesBothCourseTablesAndOnlyApprovedReviews(): void
    {
        $response = $this->signedRequest(
            'GET',
            '/internal/api/v1/demo-command-center/tutors/candidates?subject=Math&per_page=10',
            ['demo:tutors:read'],
        );
        self::assertSame(200, $response->getStatusCode(), (string) $response->getContent());
        $body = json_decode((string) $response->getContent(), true, 32, JSON_THROW_ON_ERROR);
        self::assertCount(1, $body['data']['items']);
        self::assertCount(2, $body['data']['items'][0]['courses']);
        self::assertSame(1, $body['data']['items'][0]['review_summary']['approved_review_count']);
        self::assertSame('unknown', $body['data']['items'][0]['availability_status']);
        self::assertStringNotContainsString('UNAPPROVED_REVIEW_MUST_NEVER_LEAK', (string) $response->getContent());
    }

    public function testReadProjectionsNeverExposeRestrictedRegisterFieldsOrContact(): void
    {
        $responses = [
            $this->signedRequest(
                'GET',
                '/internal/api/v1/demo-command-center/identities/resolve?register_ref=2',
                ['demo:identity:read'],
            ),
            $this->signedRequest(
                'GET',
                '/internal/api/v1/demo-command-center/profiles/2/minimum',
                ['demo:profiles:read'],
            ),
            $this->signedRequest(
                'GET',
                '/internal/api/v1/demo-command-center/tutors/2',
                ['demo:tutors:read'],
            ),
        ];
        foreach ($responses as $response) {
            self::assertSame(200, $response->getStatusCode(), (string) $response->getContent());
            $serialized = strtolower((string) $response->getContent());
            foreach (['password', 'c_password', 'otp', 'document_number', 'email', 'phone'] as $restricted) {
                self::assertStringNotContainsString($restricted, $serialized);
            }
        }
    }

    public function testTutorContactRequiresDedicatedScopeAndIsPurposeBound(): void
    {
        $payload = ['demo_ref' => 'demo-contact-0001', 'purpose' => 'demo_invitation'];
        $denied = $this->signedRequest(
            'POST',
            '/internal/api/v1/demo-command-center/tutors/2/contact-resolve',
            ['demo:tutors:read'],
            $payload,
        );
        self::assertSame(403, $denied->getStatusCode());

        $allowed = $this->signedRequest(
            'POST',
            '/internal/api/v1/demo-command-center/tutors/2/contact-resolve',
            ['demo:tutor-contact:read'],
            $payload,
        );
        self::assertSame(200, $allowed->getStatusCode(), (string) $allowed->getContent());
        $body = json_decode((string) $allowed->getContent(), true, 32, JSON_THROW_ON_ERROR);
        self::assertSame('tutor@example.invalid', $body['data']['email']);
        self::assertSame('demo_invitation', $body['data']['purpose']);
        self::assertArrayNotHasKey('phone', $body['data']);
    }

    public function testPhoneRecipientResolutionRequiresDedicatedScopesAndMasksTheRegisterPhone(): void
    {
        $payload = ['demo_ref' => 'demo-contact-0001', 'purpose' => 'demo_tutor_acceptance'];
        $denied = $this->signedRequest(
            'POST',
            '/internal/api/v1/demo-command-center/tutors/2/phone-resolve',
            ['demo:tutors:read'],
            $payload,
        );
        self::assertSame(403, $denied->getStatusCode());

        $teacher = $this->signedRequest(
            'POST',
            '/internal/api/v1/demo-command-center/tutors/2/phone-resolve',
            ['demo:tutor-phone:read'],
            $payload,
        );
        self::assertSame(200, $teacher->getStatusCode(), (string) $teacher->getContent());
        self::assertStringNotContainsString('+919000000002', (string) $teacher->getContent());
        $teacherBody = json_decode((string) $teacher->getContent(), true, 32, JSON_THROW_ON_ERROR);
        self::assertSame('register:2:phone', $teacherBody['data']['recipient_ref']);
        self::assertSame('*********0002', $teacherBody['data']['masked_phone']);
        self::assertSame('demo_tutor_acceptance', $teacherBody['data']['purpose']);

        $student = $this->signedRequest(
            'POST',
            '/internal/api/v1/demo-command-center/profiles/1/phone-resolve',
            ['demo:profile-phone:read'],
            ['demo_ref' => 'demo-contact-0001', 'purpose' => 'demo_session_link'],
        );
        self::assertSame(200, $student->getStatusCode(), (string) $student->getContent());
        self::assertStringNotContainsString('+919000000001', (string) $student->getContent());
        $studentBody = json_decode((string) $student->getContent(), true, 32, JSON_THROW_ON_ERROR);
        self::assertSame('register:1:phone', $studentBody['data']['recipient_ref']);
        self::assertSame('demo_session_link', $studentBody['data']['purpose']);
    }

    public function testSocialProofContainsOnlyExplicitlyApprovedContent(): void
    {
        $response = $this->signedRequest(
            'GET',
            '/internal/api/v1/demo-command-center/social-proof?limit=10',
            ['demo:social-proof:read'],
        );
        self::assertSame(200, $response->getStatusCode(), (string) $response->getContent());
        self::assertStringContainsString('Clear explanations', (string) $response->getContent());
        self::assertStringNotContainsString('UNAPPROVED_REVIEW', (string) $response->getContent());
    }
}
