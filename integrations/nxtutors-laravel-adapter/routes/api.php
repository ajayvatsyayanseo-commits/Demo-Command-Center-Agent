<?php

declare(strict_types=1);

use Illuminate\Support\Facades\Route;
use NxTutors\DemoCommandCenterAdapter\Http\Controllers\ApprovedPlansController;
use NxTutors\DemoCommandCenterAdapter\Http\Controllers\DemoProjectionController;
use NxTutors\DemoCommandCenterAdapter\Http\Controllers\IdentityController;
use NxTutors\DemoCommandCenterAdapter\Http\Controllers\MinimumProfileController;
use NxTutors\DemoCommandCenterAdapter\Http\Controllers\OnboardingStatusController;
use NxTutors\DemoCommandCenterAdapter\Http\Controllers\PlanQuoteController;
use NxTutors\DemoCommandCenterAdapter\Http\Controllers\ProfilePhoneController;
use NxTutors\DemoCommandCenterAdapter\Http\Controllers\ReferenceCatalogController;
use NxTutors\DemoCommandCenterAdapter\Http\Controllers\RegionMappingsController;
use NxTutors\DemoCommandCenterAdapter\Http\Controllers\SocialProofController;
use NxTutors\DemoCommandCenterAdapter\Http\Controllers\SubscriptionActivationController;
use NxTutors\DemoCommandCenterAdapter\Http\Controllers\SubscriptionStateController;
use NxTutors\DemoCommandCenterAdapter\Http\Controllers\TutorCandidatesController;
use NxTutors\DemoCommandCenterAdapter\Http\Controllers\TutorContactController;
use NxTutors\DemoCommandCenterAdapter\Http\Controllers\TutorPhoneController;
use NxTutors\DemoCommandCenterAdapter\Http\Controllers\TutorProfileController;

Route::prefix('internal/api/v1/demo-command-center')
    ->middleware([
        'demo-command-center.audit',
        'demo-command-center.auth',
        'throttle:demo-command-center-internal',
    ])
    ->group(static function (): void {
        Route::get('/identities/resolve', IdentityController::class)
            ->middleware('demo-command-center.scope:demo:identity:read')
            ->name('dcc.identities.resolve');
        Route::get('/profiles/{register}/minimum', MinimumProfileController::class)
            ->middleware('demo-command-center.scope:demo:profiles:read')
            ->name('dcc.profiles.minimum');
        Route::post('/profiles/{register}/phone-resolve', ProfilePhoneController::class)
            ->middleware('demo-command-center.scope:demo:profile-phone:read')
            ->name('dcc.profiles.phone');

        Route::get('/tutors/candidates', TutorCandidatesController::class)
            ->middleware('demo-command-center.scope:demo:tutors:read')
            ->name('dcc.tutors.candidates');
        Route::get('/tutors/{tutor}', TutorProfileController::class)
            ->middleware('demo-command-center.scope:demo:tutors:read')
            ->name('dcc.tutors.profile');
        Route::post('/tutors/{tutor}/contact-resolve', TutorContactController::class)
            ->middleware('demo-command-center.scope:demo:tutor-contact:read')
            ->name('dcc.tutors.contact');
        Route::post('/tutors/{tutor}/phone-resolve', TutorPhoneController::class)
            ->middleware('demo-command-center.scope:demo:tutor-phone:read')
            ->name('dcc.tutors.phone');

        Route::get('/reference/catalog', ReferenceCatalogController::class)
            ->middleware('demo-command-center.scope:demo:reference:read')
            ->name('dcc.reference.catalog');
        Route::get('/reference/regions', RegionMappingsController::class)
            ->middleware('demo-command-center.scope:demo:regions:read')
            ->name('dcc.reference.regions');
        Route::get('/social-proof', SocialProofController::class)
            ->middleware('demo-command-center.scope:demo:social-proof:read')
            ->name('dcc.social-proof.index');

        Route::get('/plans', ApprovedPlansController::class)
            ->middleware('demo-command-center.scope:demo:plans:read')
            ->name('dcc.plans.index');
        Route::get('/plans/{plan}/quote', PlanQuoteController::class)
            ->middleware('demo-command-center.scope:demo:plans:read')
            ->name('dcc.plans.quote');
        Route::get('/subscriptions/state', SubscriptionStateController::class)
            ->middleware('demo-command-center.scope:demo:subscriptions:read')
            ->name('dcc.subscriptions.state');
        Route::post('/subscriptions/activations', SubscriptionActivationController::class)
            ->middleware('demo-command-center.scope:demo:subscription:write')
            ->name('dcc.subscriptions.activate');

        Route::put('/demos/{demo}/projection', DemoProjectionController::class)
            ->middleware('demo-command-center.scope:demo:projection:write')
            ->name('dcc.demos.projection');
        Route::post('/demos/{demo}/onboarding-status', OnboardingStatusController::class)
            ->middleware('demo-command-center.scope:demo:onboarding:write')
            ->name('dcc.demos.onboarding');
    });
